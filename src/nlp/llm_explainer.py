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
    "ni ningún aviso legal o descargo de responsabilidad — la plataforma ya informa eso por separado.\n\n"
    "Qué debe tener la explicación: (1) qué mide el indicador, (2) qué dice este número, y "
    "(3) por qué ese número se lee así. Para (1) y (3) usa SOLO la lectura del indicador que te entrego "
    "en el mensaje: no agregues fórmulas, cortes ni cifras que no estén ahí. Explicas cómo se interpreta "
    "el dato, no las causas del movimiento del precio: no sabes por qué se movió y no debes inventarlo.\n\n"
    "Lo que NO debes hacer: no pronostiques ni digas qué hará el precio (nada de «subirá», «bajará», "
    "«seguirá», «anticipa»); no aconsejes comprar, vender o esperar. Puedes decir qué suele indicar una "
    "lectura así, siempre como interpretación del dato y no como predicción. El nivel de riesgo se calcula "
    "de forma distinta en cada indicador: cíñete a la lectura que te entrego y no lo expliques con una "
    "regla general."
)

# Lectura de cada indicador, escrita a partir de src/extractor/indicators.py (los cortes, las ventanas y
# lo que representa `value`). tests/test_llm_prompt.py compara estos textos con el codigo: si cambia una
# formula o un umbral, hay que cambiarlos aqui. La version "llano" no usa jerga ni numeros de umbral
# (nivel basico); la "tecnico" si, para intermedio y avanzado.
_INDICATOR_FACTS = {
    "rsi": {
        "llano": (
            "El RSI compara cuánto subió y cuánto bajó el precio en las últimas semanas, y lo resume en un "
            "número de 0 a 100. Un número alto quiere decir que casi todo el movimiento reciente fue hacia "
            "arriba, y uno bajo, que casi todo fue hacia abajo."
        ),
        "tecnico": (
            "RSI de Wilder de 14 sesiones, de 0 a 100: compara las subidas con las bajadas recientes. "
            "Sobre 70 se considera sobrecompra y bajo 30, sobreventa; entre 30 y 70 es zona neutral. "
            "El riesgo es alto en los extremos (sobre 70 o bajo 30)."
        ),
    },
    "macd": {
        "llano": (
            "El MACD mide si el precio está ganando o perdiendo fuerza en su movimiento. El número es la "
            "distancia entre dos líneas que siguen al precio: cuanto más grande, más fuerte es el empuje; "
            "si es positivo, el empuje es hacia arriba, y si es negativo, hacia abajo."
        ),
        "tecnico": (
            "MACD estándar (12, 26, 9). El valor es el histograma: la diferencia entre la línea MACD y su "
            "línea de señal. Positivo significa MACD sobre su señal (tendencia alcista) y negativo, bajo su "
            "señal (bajista). El riesgo depende de cuán grande es el histograma frente a su variación "
            "habitual, no de un valor fijo."
        ),
    },
    "medias_moviles": {
        "llano": (
            "Las medias móviles son el precio promedio de un período corto y de uno largo. El número es "
            "cuánto por ciento está el promedio corto por encima o por debajo del largo: si es positivo, el "
            "precio reciente está más alto que el de más largo plazo, y si es negativo, más bajo."
        ),
        "tecnico": (
            "Compara la media móvil corta con la larga; el valor es la diferencia porcentual entre ambas. "
            "Positivo significa corta sobre larga (alcista) y negativo, corta bajo larga (bajista). El "
            "ventanas son de 50 y 200 sesiones (más cortas solo si el instrumento tiene poca historia). El riesgo es mayor cuanto más separadas "
            "están las medias, en cualquier dirección."
        ),
    },
    "bandas_bollinger": {
        "llano": (
            "Las Bandas de Bollinger marcan el rango donde suele moverse el precio. El número indica en qué "
            "parte de ese rango está: cerca de 0 es la parte baja, cerca de 1 la parte alta, y fuera de ese "
            "tramo quiere decir que el precio salió de su rango habitual."
        ),
        "tecnico": (
            "Bandas de Bollinger de 20 sesiones y 2 desviaciones estándar. El valor es el %B: la posición "
            "del precio dentro de las bandas (0 en la inferior, 1 en la superior). Sobre 1 está sobre la "
            "banda superior y bajo 0, bajo la inferior. El riesgo es alto fuera de las bandas y medio cerca "
            "de sus bordes."
        ),
    },
}


def build_system_prompt(level: str) -> str:
    """System prompt del LLM: rol de educador + la ficha del nivel (levels.LEVELS).

    El nivel define COMO habla el modelo; el mensaje de usuario solo trae los datos.
    """
    ficha = LEVELS.get(level, LEVELS[DEFAULT_LEVEL])
    context = (
        "Puedes mencionar el IPSA o el mercado chileno solo si aporta algo a esta explicación; no lo "
        "repitas en cada texto."
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


# Cada estilo cambia COMO empieza y se cierra el texto, para que las explicaciones no salgan todas con el
# mismo molde. No llevan frases de ejemplo: el modelo las copiaria y la repeticion empeoraria.
_STYLE_HINTS = {
    0: (
        "Estilo directo: abre con el número y su nivel de riesgo, y después explica qué mide el indicador "
        "y por qué ese número se lee así, con frases cortas."
    ),
    1: (
        "Estilo conversacional: háblale de tú y abre con una pregunta o con lo que esa persona vería en "
        "pantalla; después explica qué dice el número y por qué se lee así."
    ),
    2: (
        "Estilo con contexto: abre explicando qué mide el indicador y, ya con eso claro, entrega el número "
        "con su nivel de riesgo y qué suele indicar una lectura así, sin predecir el precio."
    ),
}
# El nivel avanzado no explica qué mide el indicador: su tercer estilo cierra con la señal que confirmaría
# o descartaría la lectura, dicha como dato y no como consejo.
_ADVANCED_STYLE_2 = (
    "Estilo con contexto: abre con el número y su nivel de riesgo, y cierra con la señal del propio "
    "indicador que confirmaría o descartaría esa lectura, sin predecir el precio."
)


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

    # Lectura verificada del indicador (qué mide y cómo se interpreta). El nivel básico recibe la versión
    # sin jerga ni números de umbral.
    version = "llano" if detail_level == "basico" else "tecnico"
    lectura = _INDICATOR_FACTS.get(ind, {}).get(version, "")
    # El nivel avanzado no explica qué mide el indicador: solo lo usa para sostener la lectura.
    uso = (
        "úsala solo como base de tu lectura; no expliques qué mide"
        if detail_level == "avanzado"
        else "úsala para explicar qué mide y por qué el número se lee así"
    )
    bloque_lectura = f"Lectura del indicador ({uso}):\n{lectura}\n\n" if lectura else ""

    return (
        f"Empresa: {display_name}\n"
        f"Indicador: {ind_name}\n"
        f"Valor: {val_str}{' — ' + signal_desc if signal_desc else ''}\n"
        f"Nivel de riesgo: {risk_label}\n"
        "\n"
        f"{bloque_lectura}"
        f"Explica este dato siguiendo el nivel indicado. Máximo {max_words} palabras. Requisitos:\n"
        f'- Incluye el número exactamente como "{val_str}" y la frase "{risk_label}" en las primeras dos '
        "oraciones.\n"
        f"- {style_hint}\n"
        "- No empieces siempre igual: evita abrir con el nombre del indicador seguido del nombre de la "
        "empresa.\n"
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
