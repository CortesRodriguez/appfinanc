"""Generador de explicaciones mediante LLM (Groq / qwen/qwen3.8-27b).

Diseño: genera el texto de explicación en tiempo real a partir de los datos
del indicador, en lugar de seleccionar una plantilla predefinida. Esto hace
que la explicación sea única para cada combinación de instrumento + valor +
contexto de mercado, en cumplimiento con el título del proyecto ("sistema
basado en inteligencia artificial").

Fallback: si la llamada falla (red, cuota, clave inválida) lanza LLMError.
El caller en `explainer.py` captura esa excepción y cae silenciosamente al
motor de plantillas, preservando la tolerancia a fallos (RNF-09).

Restricción de coherencia: el prompt instruye explícitamente al LLM a incluir
el valor numérico exacto y la etiqueta de riesgo en español, para que el
validador de coherencia (`validator.py`) los encuentre en el texto generado.
"""

from .levels import DEFAULT_LEVEL, LEVELS

_INDICATOR_NAMES = {
    "rsi": "RSI (Índice de Fuerza Relativa)",
    "macd": "MACD (Convergencia/Divergencia de Medias Móviles)",
    "medias_moviles": "Medias Móviles",
    "bandas_bollinger": "Bandas de Bollinger (%B)",
}

_RISK_LABELS_ES = {
    "bajo": "riesgo bajo",
    "medio": "riesgo medio",
    "alto": "riesgo alto",
}

_BASE_ROLE = (
    "Eres un educador financiero especializado en el mercado chileno. "
    "Tu rol es explicar qué significa un indicador técnico, no aconsejar decisiones de inversión. "
    "Escribe siempre en español natural. "
    "No uses analogías ni metáforas: explica el dato de forma literal. "
    "Nunca incluyas frases como 'esto no es una recomendación', 'consulta a un experto' "
    "ni ningún aviso legal o descargo de responsabilidad — la plataforma ya informa eso por separado. "
    "Limítate a explicar el dato: qué dice el número y qué suele significar."
)


def build_system_prompt(level: str) -> str:
    """System prompt del LLM: rol de educador + la ficha del nivel (levels.LEVELS).

    El nivel define COMO habla el modelo; el mensaje de usuario solo trae los datos.
    """
    ficha = LEVELS.get(level, LEVELS[DEFAULT_LEVEL])
    context = (
        "Menciona brevemente el IPSA o el mercado chileno como contexto."
        if ficha["ipsa"]
        else "No agregues contexto del IPSA ni del mercado en general: solo el dato."
    )
    return (
        f"{_BASE_ROLE}\n\n"
        f"Nivel de la persona: {level.upper()}. Le hablas a {ficha['audience']}.\n"
        f"- {ficha['measures']}\n"
        f"- {ficha['vocabulary']}\n"
        f"- {ficha['thresholds']}\n"
        f"- {context}\n"
        f"- Máximo {ficha['max_words']} palabras."
    )


class LLMError(Exception):
    pass


def _signal_description(indicator_data: dict, plain: bool = False) -> str:
    """Lectura de la senal para el prompt. `plain` evita la jerga (nivel basico) para
    no inducir al modelo a repetirla."""
    ind = indicator_data.get("indicator", "")
    if plain and ind in ("rsi", "bandas_bollinger"):
        from .explainer import _LLANO, _reading_key

        return _LLANO.get(ind, {}).get(_reading_key(indicator_data), "")
    if ind == "rsi":
        sig_map = {
            "sobrecomprado": "en zona de sobrecompra (precio subió mucho en poco tiempo)",
            "sobrevendido": "en zona de sobrevenida (precio bajó mucho en poco tiempo)",
        }
        return sig_map.get(indicator_data.get("signal", ""), "en zona neutral")
    if ind in ("macd", "medias_moviles"):
        trend = indicator_data.get("trend", "")
        return f"tendencia {trend}" if trend else ""
    if ind == "bandas_bollinger":
        sig_map = {
            "sobrecomprado": "por encima del rango habitual (precio muy alto respecto a su promedio)",
            "sobrevendido": "por debajo del rango habitual (precio muy bajo respecto a su promedio)",
            "cercano_al_extremo": "cerca del límite del rango habitual",
            "normal": "dentro del rango habitual",
        }
        return sig_map.get(indicator_data.get("signal", ""), "dentro del rango habitual")
    return ""


_STYLE_HINTS = {
    0: "Tono directo: empieza por el dato y usa frases cortas.",
    1: "Tono conversacional: háblale de tú, de forma cercana.",
    2: "Cierra con qué suele pasar después de una lectura así, sin analogías.",
}
# El nivel avanzado no usa analogías: su tercer estilo mira hacia adelante.
_ADVANCED_STYLE_2 = "Cierra con qué conviene vigilar a continuación (confirmación, cruce, ruptura)."


def _build_llm_prompt(indicator_data: dict, display_name: str, detail_level: str, variant: int = 0) -> str:
    ind = indicator_data.get("indicator", "")
    value = indicator_data.get("value", 0)
    val_str = str(value)
    risk_level = indicator_data.get("risk_level", "medio")
    risk_label = _RISK_LABELS_ES.get(risk_level, "riesgo medio")
    ind_name = _INDICATOR_NAMES.get(ind, ind)
    signal_desc = _signal_description(indicator_data, plain=detail_level == "basico")
    max_words = LEVELS.get(detail_level, LEVELS[DEFAULT_LEVEL])["max_words"]

    style = variant % len(_STYLE_HINTS)
    style_hint = _ADVANCED_STYLE_2 if (detail_level == "avanzado" and style == 2) else _STYLE_HINTS[style]

    return (
        f"Empresa: {display_name}\n"
        f"Indicador: {ind_name}\n"
        f"Valor: {val_str}{' — ' + signal_desc if signal_desc else ''}\n"
        f"Nivel de riesgo: {risk_label}\n"
        "\n"
        f"Explica este dato siguiendo el nivel indicado. Máximo {max_words} palabras. Requisitos:\n"
        f'- Incluye el número exactamente como "{val_str}" y la frase "{risk_label}"\n'
        f"- {style_hint}\n"
        "\n"
        "Responde SOLO con el párrafo, sin títulos ni avisos."
    )


def generate_explanation_llm(
    indicator_data: dict,
    display_name: str,
    detail_level: str,
    api_key: str,
    model: str = "qwen/qwen3.8-27b",
    variant: int = 0,
) -> str:
    """Genera una explicación en lenguaje natural vía Groq.

    Lanza LLMError ante cualquier fallo (red, cuota, clave inválida,
    respuesta vacía). El caller debe capturar LLMError y degradar al
    motor de plantillas.
    """
    try:
        from groq import Groq  # type: ignore
    except ImportError as exc:
        raise LLMError("groq no está instalado: pip install groq") from exc

    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": build_system_prompt(detail_level)},
                {"role": "user", "content": _build_llm_prompt(indicator_data, display_name, detail_level, variant)},
            ],
            model=model,
            max_tokens=300,
            temperature=0.7,
        )
        text = response.choices[0].message.content
        if not text or not text.strip():
            raise LLMError("El LLM devolvió una respuesta vacía")
        return text.strip()
    except LLMError:
        raise
    except Exception as exc:
        raise LLMError(f"Error al llamar a Groq: {exc}") from exc
