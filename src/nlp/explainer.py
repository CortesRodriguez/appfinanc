"""Procesador NLP (RF-04, RF-05, RF-06).

Genera explicaciones en lenguaje natural, en espanol y sin
tecnicismos, a partir del valor numerico de un indicador financiero.

Diseno: FinBERT (RF-04.1) clasifica una senal de sentimiento del texto
producido por un motor de plantillas + reglas, y el resultado final se
valida contra el valor real del indicador (RF-04.2, en validator.py).
El diseno de plantillas + validador es intencional: garantiza que la
respuesta no contradiga el dato numerico incluso si el modelo alucina.

FinBERT esta activo por defecto (RF-04.1). Si `transformers`/`torch` no
estan instalados o el modelo falla, la senal cae silenciosamente a None
y las plantillas siguen produciendo una explicacion valida (fallback
silencioso, coherente con la tolerancia a fallos de RNF-09).
"""

import os

from .readability import fernandez_huerta_score

MAX_WORDS = 150

NATIONAL_REFERENCES = {
    "rsi": [
        "Este tipo de señales suelen leerse junto al comportamiento general del IPSA, para no sacar conclusiones solo con un instrumento.",
    ],
    "medias_moviles": [
        "Comparar esta tendencia con el desempeño del IPSA ayuda a saber si el movimiento es propio del instrumento o de todo el mercado chileno.",
    ],
    "macd": [
        "Vale la pena mirar cómo se ve esta señal en el IPSA en el mismo período, para saber si el impulso es propio del instrumento o del mercado chileno en general.",
    ],
    "bandas_bollinger": [
        "En un mercado como el chileno, con volumen acotado, es útil comparar esta lectura con lo que ocurre en el IPSA en las mismas fechas.",
    ],
}

RISK_LABELS = {"bajo": "riesgo bajo", "medio": "riesgo medio", "alto": "riesgo alto"}

# RF-13.2 / RF-18.3: frase adicional para el nivel de detalle "detallado", usada cuando el
# perfil de aprendizaje del usuario indica que le ha costado comprender un indicador
# (varias solicitudes de regeneracion registradas para ese indicador).
DETAIL_EXTRAS = {
    "rsi": "En términos simples: este número solo compara qué tan fuertes fueron las subidas frente a las bajadas recientes; no predice con certeza lo que vendrá.",
    "medias_moviles": "En términos simples: comparar un promedio de precio reciente con uno más antiguo es una forma habitual de detectar si el precio está cambiando de dirección.",
    "macd": "En términos simples: el MACD compara un promedio de precios rápido con uno más lento; cuando el rápido sube por encima del lento se interpreta como que el precio está tomando impulso al alza.",
    "bandas_bollinger": "En términos simples: las Bandas de Bollinger marcan un rango habitual de variación del precio; cuando el precio se sale del rango puede significar que el mercado se emocionó (subida o bajada fuerte de corto plazo).",
}

TEMPLATES = {
    "rsi": {
        "bajo": [
            "El RSI de {symbol} es {value} puntos, en una zona neutral. No hay señales claras de sobrecompra ni de sobreventa "
            "en este momento ({risk_label} asociado a esta lectura).",
            "{symbol} tiene un RSI de {value} puntos ({risk_label}). Se encuentra en un rango tranquilo, sin señales extremas "
            "en el corto plazo.",
            "El RSI de {symbol} está en {value} puntos ({risk_label}), un valor moderado que no sugiere presiones fuertes "
            "ni de compra ni de venta.",
        ],
        "medio": [
            "El RSI de {symbol} es {value} puntos ({risk_label}). Se ubica en un rango intermedio, sin señales extremas de "
            "compra o venta excesiva.",
            "{symbol} muestra un RSI de {value} puntos ({risk_label}), en una zona intermedia que conviene observar antes de "
            "sacar conclusiones.",
            "El RSI de {symbol} llega a {value} puntos ({risk_label}), un valor que refleja actividad reciente sin ser aún "
            "una señal contundente.",
        ],
        "alto": [
            "El RSI de {symbol} es {value} puntos ({risk_label}). Un valor tan alto o tan bajo suele indicar que el "
            "instrumento fue comprado o vendido en exceso recientemente, lo que podría anticipar un cambio de tendencia.",
            "{symbol} presenta un RSI de {value} puntos ({risk_label}), lectura que sugiere una zona extrema donde suele "
            "haber una corrección de precio en los días siguientes.",
            "El RSI de {symbol} alcanza {value} puntos ({risk_label}), un nivel poco común que suele preceder a "
            "movimientos de reversión en el corto plazo.",
        ],
    },
    "medias_moviles": {
        "bajo": [
            "Comparando el promedio de precios reciente con el más antiguo, {symbol} muestra una tendencia {trend} leve "
            "de {value}% ({risk_label}), sin una dirección demasiado marcada.",
            "{symbol} tiene una tendencia {trend} de {value}% al comparar sus dos promedios de precio ({risk_label}), un "
            "movimiento pequeño y sin fuerza clara.",
            "La diferencia entre los promedios de precio de {symbol} es de {value}% en dirección {trend} ({risk_label}), "
            "una señal suave de la evolución del precio.",
        ],
        "medio": [
            "{symbol} muestra una tendencia {trend} de {value}% al comparar sus promedios de precio reciente y anterior "
            "({risk_label}).",
            "Los promedios de precio de {symbol} muestran una tendencia {trend} de {value}% ({risk_label}), un movimiento "
            "moderado en esa dirección.",
            "{symbol} refleja una tendencia {trend} de {value}% entre sus dos promedios de precio ({risk_label}), un "
            "cambio notorio aunque no extremo.",
        ],
        "alto": [
            "{symbol} presenta una tendencia {trend} marcada de {value}% entre sus promedios de precio reciente y "
            "anterior ({risk_label}), lo que sugiere un movimiento de precio con fuerza en esa dirección.",
            "Los promedios de precio de {symbol} indican una tendencia {trend} pronunciada de {value}% ({risk_label}), "
            "señal de un movimiento sostenido en el tiempo.",
            "{symbol} muestra una tendencia {trend} fuerte de {value}% ({risk_label}) entre sus promedios de precio, "
            "un cambio de dirección con impulso relevante.",
        ],
    },
    "macd": {
        "bajo": [
            "El MACD de {symbol} muestra una señal {trend} suave (histograma en {value} puntos, {risk_label}). El precio "
            "no tiene un impulso fuerte hacia arriba ni hacia abajo en este momento.",
            "{symbol} presenta un MACD {trend} con histograma de {value} puntos ({risk_label}). Es una señal tranquila, "
            "sin fuerza clara de subida ni de bajada.",
            "El histograma del MACD de {symbol} está en {value} puntos, con lectura {trend} ({risk_label}). Un valor así "
            "sugiere un mercado sin dirección marcada.",
        ],
        "medio": [
            "El MACD de {symbol} tiene una señal {trend} con histograma de {value} puntos ({risk_label}). El precio "
            "muestra un impulso moderado en esa dirección.",
            "{symbol} entrega una lectura {trend} en el MACD (histograma {value}, {risk_label}). Es una señal a observar, "
            "aunque aún no es contundente.",
            "El MACD de {symbol} apunta a una tendencia {trend} intermedia ({value} pts en el histograma, {risk_label}), "
            "consistente con un cambio de ritmo del precio.",
        ],
        "alto": [
            "El MACD de {symbol} muestra una señal {trend} fuerte (histograma de {value} puntos, {risk_label}). Un valor "
            "así indica que el precio está tomando impulso pronunciado en esa dirección.",
            "{symbol} presenta un MACD con lectura {trend} marcada (histograma {value}, {risk_label}), señal de un "
            "movimiento con inercia sostenida.",
            "El histograma del MACD de {symbol} alcanza {value} puntos ({trend}, {risk_label}), un nivel elevado que "
            "suele acompañar movimientos de precio pronunciados.",
        ],
    },
    "bandas_bollinger": {
        "bajo": [
            "El indicador %B de {symbol} es {value} ({risk_label}). El precio se mueve dentro del rango habitual definido "
            "por las Bandas de Bollinger, sin extremos.",
            "{symbol} tiene un %B de {value} ({risk_label}), lo que ubica al precio en el centro del rango habitual, sin "
            "señales de estrés en la cotización.",
            "La lectura de las Bandas de Bollinger para {symbol} entrega un %B de {value} ({risk_label}), consistente con "
            "un precio dentro de sus márgenes normales.",
        ],
        "medio": [
            "El %B de {symbol} es {value} ({risk_label}). El precio se acerca a uno de los bordes del rango habitual, lo "
            "que a veces anticipa un movimiento más marcado en los días siguientes.",
            "{symbol} tiene un %B de {value} ({risk_label}), rozando los extremos del rango. Es momento de observar la "
            "evolución del precio con más atención.",
            "La lectura %B de {symbol} está en {value} ({risk_label}), señalando que el precio está acercándose a un "
            "límite del rango habitual.",
        ],
        "alto": [
            "El %B de {symbol} es {value} ({risk_label}). El precio se salió del rango habitual, señal de que el mercado "
            "reaccionó con fuerza a la baja o al alza en el muy corto plazo.",
            "{symbol} presenta un %B de {value} ({risk_label}), un valor fuera del rango típico. Suele leerse como una "
            "reacción intensa que puede revertirse en los próximos días.",
            "La lectura de Bandas de Bollinger para {symbol} arroja un %B de {value} ({risk_label}), señal de que el "
            "precio se ha desviado del rango habitual y podría corregir en breve.",
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


# Cache del pipeline de FinBERT: se instancia una sola vez por proceso.
# `_finbert_state` puede ser:
#   None             -> aun no se ha intentado cargar (lazy init)
#   {"pipe": p}      -> cargado y listo, se reutiliza en cada llamada
#   {"pipe": None}   -> intento fallido; no reintentar mas (evita colgarse
#                       repitiendo el HEAD a huggingface.co con red inestable)
_finbert_state = None


def _load_finbert():
    """Carga (o recupera del cache) el pipeline de FinBERT.

    Antes cada llamada a `_finbert_signal` construia el pipeline desde cero,
    lo que dispara un HEAD contra `huggingface.co/ProsusAI/finbert` para
    revisar si el modelo cambio. Con la red bloqueando ese handshake SSL,
    huggingface_hub reintenta 5 x 8s antes de rendirse -> el dashboard
    quedaba esperando ~40s por cada uno de los 4 indicadores paralelos.

    Estrategia:
    1. Cachear el resultado del primer intento por todo el proceso. Si
       funciono, se reutiliza; si fallo, futuros calls saltan directo al
       fallback silencioso sin reintentar la red.
    2. Forzar `HF_HUB_OFFLINE=1` / `TRANSFORMERS_OFFLINE=1` antes del
       import. Si el modelo ya esta en `~/.cache/huggingface`, se carga
       instantaneamente sin HEAD remoto. Si nunca se descargo, el error
       es inmediato en vez de colgarse 40s reintentando SSL.
    """
    global _finbert_state
    if _finbert_state is not None:
        return _finbert_state["pipe"]

    # Debe estar seteado antes del import de transformers / huggingface_hub
    # (se leen al importar). Si ya estan importados por otro modulo, los
    # respetan igual: huggingface_hub los relee en cada llamada de red.
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    try:
        from transformers import pipeline  # type: ignore

        pipe = pipeline("sentiment-analysis", model="ProsusAI/finbert")
        _finbert_state = {"pipe": pipe}
        return pipe
    except Exception:  # noqa: BLE001 - degradacion silenciosa por diseno
        _finbert_state = {"pipe": None}
        return None


def _finbert_signal(text: str):
    """Senal de sentimiento de FinBERT (RF-04.1) con fallback silencioso.

    FinBERT es el componente clasificador por diseno. Si por cualquier razon
    (`transformers`/`torch` no instalados, error de carga del modelo, timeout)
    la clasificacion falla, la funcion retorna None y las plantillas siguen
    produciendo una explicacion valida. Esta degradacion silenciosa es
    coherente con la tolerancia a fallos de RNF-09.
    """
    classifier = _load_finbert()
    if classifier is None:
        return None
    try:
        result = classifier(text[:512])[0]
        return {"label": result["label"], "score": round(float(result["score"]), 3)}
    except Exception:  # noqa: BLE001 - degradacion silenciosa por diseno
        return None


def generate_explanation(
    indicator_data: dict,
    variant: int = 0,
    use_finbert: bool = True,
    include_national_reference: bool = True,
    detail_level: str = "estandar",
):
    """Genera una explicacion en lenguaje natural para un indicador extraido.

    `indicator_data` es el dict retornado por `extractor.get_indicator`.
    `variant` selecciona una redaccion alternativa (RF-06.2, CU-13).
    `use_finbert=True` por defecto (RF-04.1). Si el modelo no esta disponible,
    la senal queda en None y las plantillas siguen operando.
    `detail_level` ("estandar" | "detallado") ajusta la extension segun el
    perfil de aprendizaje del usuario (RF-13.2).
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


def regenerate_explanation(indicator_data: dict, previous_variant: int, use_finbert: bool = True, detail_level: str = "estandar"):
    """Genera una redaccion alternativa distinta a la anterior (RF-06.2, CU-13)."""
    indicator = indicator_data["indicator"]
    risk_level = indicator_data["risk_level"]
    pool_size = len(TEMPLATES[indicator][risk_level])

    if pool_size <= 1:
        # No hay una redaccion alternativa disponible para este caso
        return generate_explanation(indicator_data, variant=previous_variant, use_finbert=use_finbert, detail_level=detail_level)

    next_variant = (previous_variant + 1) % pool_size
    return generate_explanation(indicator_data, variant=next_variant, use_finbert=use_finbert, detail_level=detail_level)
