"""Procesador NLP (RF-04, RF-05, RF-06).

Genera explicaciones en lenguaje natural, en espanol, a partir del valor
numerico de un indicador financiero, con el nivel de explicacion del usuario
(basico / intermedio / avanzado, ver levels.py; plantillas en templates.py).

Diseno: con `use_llm` activo, un LLM (Groq) redacta el texto segun la ficha
del nivel; se acepta solo si cita la etiqueta de riesgo y el valor, respeta el
vocabulario del nivel y pasa el validador de coherencia (RF-04.2, validator.py).
Si no, o si el LLM falla, se usan las plantillas (templates.py), coherentes con
el dato por construccion. Despues, la ruta vuelve a validar el texto final y
avisa si discrepa.

FinBERT (RF-04.1) es opcional: solo agrega una etiqueta de sentimiento y no
participa en la redaccion. Si `transformers`/`torch` no estan instalados o el
modelo falla, la senal cae silenciosamente a None (fallback silencioso,
coherente con la tolerancia a fallos de RNF-09).
"""

import os

from .readability import fernandez_huerta_score

from .levels import DEFAULT_LEVEL, LEVELS, contains_forbidden_term, level_max_words
from .templates import NATIONAL_REFERENCES, STYLE_LABELS, TEMPLATES  # noqa: F401 - API publica

# Tope absoluto; cada nivel tiene el suyo, mas bajo (levels.LEVELS[nivel]["max_words"]).
MAX_WORDS = 150

RISK_LABELS = {"bajo": "riesgo bajo", "medio": "riesgo medio", "alto": "riesgo alto"}

# Lectura tecnica de la senal, con el umbral que la define (marcador {zona}).
_ZONA = {
    "rsi": {
        "sobrecomprado": "en sobrecompra (sobre 70)",
        "sobrevendido": "en sobreventa (bajo 30)",
        "neutral": "entre 30 y 70, zona neutral",
    },
    "medias_moviles": {
        "alcista": "la media corta está sobre la larga",
        "bajista": "la media corta está bajo la larga",
    },
    "macd": {
        "alcista": "MACD sobre su línea de señal",
        "bajista": "MACD bajo su línea de señal",
    },
    "bandas_bollinger": {
        "sobrecomprado": "sobre la banda superior (%B mayor que 1)",
        "sobrevendido": "bajo la banda inferior (%B menor que 0)",
        "cercano_superior": "cerca de la banda superior (%B cerca de 1)",
        "cercano_inferior": "cerca de la banda inferior (%B cerca de 0)",
        "normal": "dentro de las bandas, lejos de los extremos",
    },
}

# La misma lectura sin jerga (marcador {llano}).
_LLANO = {
    "rsi": {
        "sobrecomprado": "subió muy rápido en poco tiempo",
        "sobrevendido": "bajó muy rápido en poco tiempo",
        "neutral": "se ha movido con calma",
    },
    "bandas_bollinger": {
        "sobrecomprado": "por encima del techo de su rango",
        "sobrevendido": "por debajo del piso de su rango",
        "cercano_superior": "cerca del techo de su rango",
        "cercano_inferior": "cerca del piso de su rango",
        "normal": "en la zona media de su rango",
    },
}

_DIR = {"alcista": "hacia arriba", "bajista": "hacia abajo"}


def _reading_key(data: dict) -> str:
    """Clave de lectura del indicador: la senal (RSI/Bollinger) o la tendencia (MA/MACD)."""
    indicator = data.get("indicator", "")
    if indicator in ("medias_moviles", "macd"):
        return data.get("trend", "alcista")
    signal = data.get("signal", "neutral" if indicator == "rsi" else "normal")
    if signal == "cercano_al_extremo":
        return "cercano_superior" if data.get("value", 0) >= 0.5 else "cercano_inferior"
    return signal


def _normalize_level(detail_level: str) -> str:
    return detail_level if detail_level in LEVELS else DEFAULT_LEVEL


def _build_finbert_input(indicator_data: dict) -> str:
    """Construye una frase financiera corta en inglés para FinBERT.

    FinBERT (ProsusAI/finbert) fue entrenado sobre noticias financieras y
    filings SEC en inglés. Pasarle las explicaciones en español produce
    resultados poco confiables. Esta función construye un input en inglés
    descriptivo del estado del indicador para que el modelo opere en su
    dominio de entrenamiento.
    """
    ind = indicator_data.get("indicator", "")
    sym = indicator_data.get("symbol", "").replace(".SN", "")
    val = indicator_data.get("value", 0)

    if ind == "rsi":
        sig_map = {"sobrecomprado": "overbought", "sobrevendido": "oversold"}
        sig = sig_map.get(indicator_data.get("signal", ""), "neutral")
        return f"{sym} RSI at {val}, {sig}"

    if ind == "macd":
        eng = "bullish" if indicator_data.get("trend") == "alcista" else "bearish"
        return f"{sym} MACD {eng}, histogram {val}"

    if ind == "medias_moviles":
        eng = "bullish" if indicator_data.get("trend") == "alcista" else "bearish"
        return f"{sym} moving averages {eng} trend, {val}%"

    if ind == "bandas_bollinger":
        sig_map = {
            "sobrecomprado": "overbought",
            "sobrevendido": "oversold",
            "cercano_al_extremo": "near extreme",
            "normal": "normal",
        }
        sig = sig_map.get(indicator_data.get("signal", ""), "normal")
        return f"{sym} Bollinger Bands %B {val}, {sig}"

    return f"{sym} {ind} {val}"


def _fill_template(template: str, data: dict, display_name: str = "") -> str:
    name = display_name if display_name else data.get("symbol", "").replace(".SN", "")
    indicator = data.get("indicator", "")
    key = _reading_key(data)
    return template.format(
        symbol=name,
        value=data.get("value", ""),
        risk_label=RISK_LABELS.get(data.get("risk_level", "medio"), "riesgo medio"),
        trend=data.get("trend", "estable"),
        zona=_ZONA.get(indicator, {}).get(key, ""),
        llano=_LLANO.get(indicator, {}).get(key, ""),
        dir=_DIR.get(data.get("trend", ""), "de lado"),
    )


def _trim_to_max_words(text: str, max_words: int = MAX_WORDS) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    cut = " ".join(words[:max_words])
    # Preferir cortar en el ultimo fin de oracion si conserva buena parte del texto.
    last_stop = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
    if last_stop > 0 and len(cut[: last_stop + 1].split()) >= max_words * 0.6:
        return cut[: last_stop + 1]
    return cut.rstrip(",.;:") + "."


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


def _is_coherent(indicator_data: dict, text: str) -> bool:
    # Import tardio: validator.py importa RISK_LABELS de este modulo.
    from .validator import validate_coherence

    return validate_coherence(indicator_data, text)[0]


def generate_explanation(
    indicator_data: dict,
    variant: int = 0,
    use_finbert: bool = True,
    include_national_reference: bool = True,
    detail_level: str = DEFAULT_LEVEL,
    display_name: str = "",
    use_llm: bool = False,
    llm_api_key: str = "",
):
    """Genera una explicacion en lenguaje natural para un indicador extraido.

    `indicator_data` es el dict retornado por `extractor.get_indicator`.
    `variant` selecciona una redaccion alternativa (RF-06.2, CU-13) y fija el estilo.
    `use_finbert=True` por defecto (RF-04.1). Si el modelo no esta disponible,
    la senal queda en None y las plantillas siguen operando.
    `detail_level` ("basico" | "intermedio" | "avanzado", ver levels.py) define como
    se explica: vocabulario, umbrales, contexto IPSA y extension (RF-13.2).
    `display_name` reemplaza el ticker en las plantillas por el nombre de la
    empresa (ej. "Banco de Chile" en vez de "CHILE.SN").
    `use_llm=True` intenta generar la explicacion con un LLM via Groq antes de
    recurrir a las plantillas. Degradacion silenciosa si falla (RNF-09).
    """
    indicator = indicator_data["indicator"]
    risk_level = indicator_data["risk_level"]
    detail_level = _normalize_level(detail_level)
    max_words = level_max_words(detail_level)

    # Intento LLM (degradacion silenciosa a plantillas si falla o incoherente)
    if use_llm and llm_api_key:
        try:
            from .llm_explainer import generate_explanation_llm
            _name = display_name or indicator_data.get("symbol", "").replace(".SN", "")
            llm_text = generate_explanation_llm(indicator_data, _name, detail_level, llm_api_key, variant=variant)
            # Verificacion: el texto debe contener el risk_label y el valor numerico,
            # respetar el vocabulario del nivel (el basico no admite jerga) y pasar el
            # validador de coherencia (que detecta, p. ej., "15.0" donde el valor es 5.0 o
            # "sobrecomprado" con RSI bajo). Si falla, se usan las plantillas.
            # Se verifica DESPUES de recortar: el recorte no debe quitar el riesgo ni el valor.
            _risk_label = RISK_LABELS.get(risk_level, "")
            _val_str = str(indicator_data.get("value", ""))
            llm_text = _trim_to_max_words(llm_text, max_words)
            if (
                _risk_label
                and _risk_label in llm_text.lower()
                and _val_str in llm_text
                and not contains_forbidden_term(detail_level, llm_text)
                and _is_coherent(indicator_data, llm_text)
            ):
                readability = fernandez_huerta_score(llm_text)
                finbert_input = _build_finbert_input(indicator_data) if use_finbert else None
                finbert_signal = _finbert_signal(finbert_input) if finbert_input else None
                return {
                    "text": llm_text,
                    "risk_level": risk_level,
                    "variant": variant,
                    "readability_score": readability,
                    "finbert_signal": finbert_signal,
                    "detail_level": detail_level,
                }
        except Exception:  # noqa: BLE001 - degradacion silenciosa por diseno
            pass

    pool = TEMPLATES[detail_level][indicator][risk_level]
    template = pool[variant % len(pool)]
    text = _fill_template(template, indicator_data, display_name=display_name)

    if include_national_reference and LEVELS[detail_level]["ipsa"] and indicator in NATIONAL_REFERENCES:
        refs = NATIONAL_REFERENCES[indicator]
        text = f"{text} {refs[variant % len(refs)]}"

    text = _trim_to_max_words(text, max_words)

    finbert_input = _build_finbert_input(indicator_data) if use_finbert else None
    finbert_signal = _finbert_signal(finbert_input) if finbert_input else None
    readability = fernandez_huerta_score(text)

    return {
        "text": text,
        "risk_level": risk_level,
        "variant": variant,
        "readability_score": readability,
        "finbert_signal": finbert_signal,
        "detail_level": detail_level,
    }


def regenerate_explanation(indicator_data: dict, previous_variant: int, use_finbert: bool = True, detail_level: str = DEFAULT_LEVEL, display_name: str = "", use_llm: bool = False, llm_api_key: str = ""):
    """Genera una redaccion alternativa distinta a la anterior (RF-06.2, CU-13)."""
    indicator = indicator_data["indicator"]
    risk_level = indicator_data["risk_level"]
    pool_size = len(TEMPLATES[_normalize_level(detail_level)][indicator][risk_level])

    if pool_size <= 1:
        return generate_explanation(indicator_data, variant=previous_variant, use_finbert=use_finbert, detail_level=detail_level, display_name=display_name, use_llm=use_llm, llm_api_key=llm_api_key)

    next_variant = (previous_variant + 1) % pool_size
    return generate_explanation(indicator_data, variant=next_variant, use_finbert=use_finbert, detail_level=detail_level, display_name=display_name, use_llm=use_llm, llm_api_key=llm_api_key)
