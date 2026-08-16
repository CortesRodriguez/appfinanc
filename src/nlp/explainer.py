"""Procesador NLP (RF-04, RF-05, RF-06).

Genera explicaciones en lenguaje natural, en espanol y sin
tecnicismos, a partir del valor numerico de un indicador financiero.
Usa un enfoque de plantillas + reglas (rapido, predecible y facil de
validar contra el valor real, RF-04.2) y, opcionalmente, una senal de
sentimiento de FinBERT si la libreria `transformers` esta instalada y
habilitada (RF-04.1: "FinBERT u otro modelo NLP equivalente").

El diseno hibrido (reglas + modelo opcional) es intencional: garantiza
que el sistema siga funcionando y cumpliendo RNF-01.1 (respuesta <= 5s)
incluso si el modelo de lenguaje no esta disponible u ocurre un error,
lo que ademas satisface RNF-08 (tolerancia a fallas).
"""

from .readability import fernandez_huerta_score

MAX_WORDS = 150

NATIONAL_REFERENCES = {
    "rentabilidad": [
        "Como referencia, la TPM (tasa de interés que fija el Banco Central) es un punto de comparación útil para saber si esta rentabilidad supera el costo del dinero en Chile.",
        "Vale la pena compararlo con el IPC del último período, para saber si la ganancia realmente le gana a la inflación.",
    ],
    "volatilidad": [
        "Para dimensionarlo, el IPSA suele moverse con menor volatilidad que una sola acción, por lo que este nivel conviene compararlo con el mercado en su conjunto.",
    ],
    "rsi": [
        "Este tipo de señales suelen leerse junto al comportamiento general del IPSA, para no sacar conclusiones solo con un instrumento.",
    ],
    "medias_moviles": [
        "Comparar esta tendencia con el desempeño del IPSA ayuda a saber si el movimiento es propio del instrumento o de todo el mercado chileno.",
    ],
}

RISK_LABELS = {"bajo": "riesgo bajo", "medio": "riesgo medio", "alto": "riesgo alto"}

# RF-18.3: frase adicional para el nivel de detalle "detallado", usada cuando el
# perfil de aprendizaje del usuario indica que le ha costado comprender un indicador
# (varias solicitudes de regeneracion registradas para ese indicador).
DETAIL_EXTRAS = {
    "volatilidad": "En términos simples: mientras más alta es la volatilidad, más te puede sorprender el precio de un día para otro, tanto para bien como para mal.",
    "rsi": "En términos simples: este número solo compara qué tan fuertes fueron las subidas frente a las bajadas recientes; no predice con certeza lo que vendrá.",
    "medias_moviles": "En términos simples: comparar un promedio de precio reciente con uno más antiguo es una forma habitual de detectar si el precio está cambiando de dirección.",
    "rentabilidad": "En términos simples: este porcentaje resume cuánto habría ganado o perdido alguien que invirtió al inicio del período y vendió al final.",
}

TEMPLATES = {
    "volatilidad": {
        "bajo": [
            "La volatilidad de {symbol} en el período consultado es de {value}%, lo que se considera {risk_label}. "
            "Esto significa que el precio se ha movido de forma relativamente estable, sin grandes sobresaltos en el corto plazo.",
            "{symbol} muestra una volatilidad de {value}% ({risk_label}), es decir, sus variaciones de precio han sido moderadas "
            "en comparación con instrumentos más agitados.",
        ],
        "medio": [
            "La volatilidad de {symbol} es de {value}% ({risk_label}). Esto indica que el precio ha tenido variaciones "
            "notorias, por lo que conviene estar atento antes de tomar decisiones apresuradas.",
        ],
        "alto": [
            "La volatilidad de {symbol} alcanza {value}% ({risk_label}). Un valor así indica movimientos de precio bruscos "
            "y poco predecibles, lo que aumenta la incertidumbre de una inversión en este instrumento.",
            "{symbol} presenta una volatilidad elevada de {value}% ({risk_label}), señal de que su precio puede subir o "
            "bajar de forma abrupta en pocos días.",
        ],
    },
    "rsi": {
        "bajo": [
            "El RSI de {symbol} es {value} puntos, en una zona neutral. No hay señales claras de sobrecompra ni de sobreventa "
            "en este momento ({risk_label} asociado a esta lectura)."
        ],
        "medio": [
            "El RSI de {symbol} es {value} puntos ({risk_label}). Se ubica en un rango intermedio, sin señales extremas de "
            "compra o venta excesiva."
        ],
        "alto": [
            "El RSI de {symbol} es {value} puntos ({risk_label}). Un valor tan alto o tan bajo suele indicar que el "
            "instrumento fue comprado o vendido en exceso recientemente, lo que podría anticipar un cambio de tendencia.",
        ],
    },
    "medias_moviles": {
        "bajo": [
            "Comparando el promedio de precios reciente con el más antiguo, {symbol} muestra una tendencia {trend} leve "
            "de {value}% ({risk_label}), sin una dirección demasiado marcada.",
        ],
        "medio": [
            "{symbol} muestra una tendencia {trend} de {value}% al comparar sus promedios de precio reciente y anterior "
            "({risk_label}).",
        ],
        "alto": [
            "{symbol} presenta una tendencia {trend} marcada de {value}% entre sus promedios de precio reciente y "
            "anterior ({risk_label}), lo que sugiere un movimiento de precio con fuerza en esa dirección.",
        ],
    },
    "rentabilidad": {
        "bajo": [
            "En el período consultado, {symbol} tuvo una rentabilidad de {value}% ({risk_label}). Es una ganancia acotada, "
            "por lo que conviene evaluarla junto a otros indicadores antes de decidir.",
        ],
        "medio": [
            "{symbol} obtuvo una rentabilidad de {value}% en el período ({risk_label}). Es un resultado a considerar, "
            "aunque el desempeño pasado no garantiza resultados futuros.",
        ],
        "alto": [
            "{symbol} tuvo una variación de {value}% en el período, clasificada como {risk_label}. Cambios tan grandes "
            "en poco tiempo suelen venir acompañados de mayor incertidumbre sobre el futuro del instrumento.",
        ],
    },
}


def _fill_template(template: str, data: dict) -> str:
    return template.format(
        symbol=data.get("symbol", ""),
        value=data.get("value", ""),
        risk_label=RISK_LABELS.get(data.get("risk_level", "medio"), "riesgo medio"),
        trend=data.get("trend", "estable"),
    )


def _trim_to_max_words(text: str, max_words: int = MAX_WORDS) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]).rstrip(",.;") + "."


def _finbert_signal(text: str):
    """Senal opcional de sentimiento de FinBERT (RF-04.1). Degradacion segura."""
    try:
        from transformers import pipeline  # type: ignore

        classifier = pipeline("sentiment-analysis", model="ProsusAI/finbert")
        result = classifier(text[:512])[0]
        return {"label": result["label"], "score": round(float(result["score"]), 3)}
    except Exception:  # noqa: BLE001 - ausencia de transformers/torch o error de modelo
        return None


def generate_explanation(
    indicator_data: dict,
    variant: int = 0,
    use_finbert: bool = False,
    include_national_reference: bool = True,
    detail_level: str = "estandar",
):
    """Genera una explicacion en lenguaje natural para un indicador extraido.

    `indicator_data` es el dict retornado por `extractor.get_indicator`.
    `variant` selecciona una redaccion alternativa (RF-06.2, CU-04).
    `detail_level` ("estandar" | "detallado") ajusta la extension segun el
    perfil de aprendizaje del usuario (RF-18.3): un indicador que el
    usuario ha regenerado varias veces se explica con mas contexto.
    """
    indicator = indicator_data["indicator"]
    risk_level = indicator_data["risk_level"]
    detailed = detail_level == "detallado"

    pool = TEMPLATES[indicator][risk_level]
    template = pool[variant % len(pool)]
    text = _fill_template(template, indicator_data)

    if (include_national_reference or detailed) and indicator in NATIONAL_REFERENCES:
        refs = NATIONAL_REFERENCES[indicator]
        text = f"{text} {refs[variant % len(refs)]}"

    if detailed and indicator in DETAIL_EXTRAS:
        text = f"{text} {DETAIL_EXTRAS[indicator]}"

    text = _trim_to_max_words(text)

    finbert_signal = _finbert_signal(text) if use_finbert else None
    readability = fernandez_huerta_score(text)

    return {
        "text": text,
        "risk_level": risk_level,
        "variant": variant,
        "readability_score": readability,
        "finbert_signal": finbert_signal,
        "detail_level": detail_level,
    }


def regenerate_explanation(indicator_data: dict, previous_variant: int, use_finbert: bool = False, detail_level: str = "estandar"):
    """Genera una redaccion alternativa distinta a la anterior (RF-06.2, CU-04)."""
    indicator = indicator_data["indicator"]
    risk_level = indicator_data["risk_level"]
    pool_size = len(TEMPLATES[indicator][risk_level])

    if pool_size <= 1:
        # No hay una redaccion alternativa disponible para este caso (Excepcion 1, CU-04)
        return generate_explanation(indicator_data, variant=previous_variant, use_finbert=use_finbert, detail_level=detail_level)

    next_variant = (previous_variant + 1) % pool_size
    return generate_explanation(indicator_data, variant=next_variant, use_finbert=use_finbert, detail_level=detail_level)
