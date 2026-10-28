"""Niveles de explicacion (RF-13.2): fuente unica de la "ficha" de cada nivel.

El nivel define COMO se explica un indicador. Lo usan dos consumidores:
  - el LLM (`llm_explainer.build_system_prompt`) lo recibe como instrucciones;
  - las plantillas de respaldo (`explainer.TEMPLATES[nivel]`) se redactan siguiendo
    la misma ficha, y los tests comprueban que la cumplan.

Los niveles estan ligados a la experiencia declarada (`users.experience_level`) y
bajan un escalon cada `DETAIL_THRESHOLD` "No entendi esto" en un indicador.
"""

LEVEL_ORDER = ("basico", "intermedio", "avanzado")

DEFAULT_LEVEL = "intermedio"

# experiencia declarada (auth.service.EXPERIENCE_LEVELS) -> nivel inicial
EXPERIENCE_TO_LEVEL = {
    "nunca": "basico",
    "poco": "intermedio",
    "experiencia": "avanzado",
}

LEVEL_LABELS = {"basico": "Básico", "intermedio": "Intermedio", "avanzado": "Avanzado"}

LEVELS = {
    "basico": {
        "audience": "una persona que nunca ha invertido y no conoce el vocabulario financiero",
        "measures": (
            "Explica SIEMPRE qué mide el indicador, con palabras simples y el dato concreto. "
            "No uses analogías ni compares con objetos (autos, termómetros, corredores, pasillos)."
        ),
        "vocabulary": (
            "Usa solo palabras de todos los días. No uses estos términos: "
            "momentum, divergencia, sobrecomprado, sobrecompra, sobrevendido, sobreventa, histograma, volatilidad, "
            "umbral, soporte, resistencia."
        ),
        "thresholds": "No menciones números de umbral (como 70, 30 o 0 y 1); basta con el valor del dato.",
        "ipsa": True,
        "max_words": 90,
        # Lista usada para descartar la salida del LLM y para el test de las plantillas.
        "forbidden_terms": (
            "momentum",
            "divergencia",
            "sobrecompr",
            "sobrevendid",
            "sobreventa",
            "histograma",
            "volatilidad",
            "umbral",
            "soporte",
            "resistencia",
            # metaforas: el nivel basico explica de forma literal
            "termómetro",
            "corredor",
            "pedal",
            "pasillo",
            "carretera",
        ),
    },
    "intermedio": {
        "audience": "una persona que sabe qué es una acción pero no conoce los indicadores técnicos",
        "measures": "Explica en UNA frase corta qué mide el indicador.",
        "vocabulary": (
            "Puedes nombrar el término técnico, pero tradúcelo enseguida "
            "(por ejemplo: 'sobrecompra, es decir, subió muy rápido')."
        ),
        "thresholds": "Nombra el umbral que corresponde (RSI 70 y 30; %B entre 0 y 1; cruce de medias).",
        "ipsa": True,
        "max_words": 60,
        "forbidden_terms": (),
    },
    "avanzado": {
        "audience": "una persona con experiencia que ya conoce el análisis técnico",
        "measures": "NO expliques qué mide el indicador ni uses analogías: ve directo a la lectura.",
        "vocabulary": "Usa vocabulario técnico con naturalidad (momentum, cruce de señal, agotamiento, divergencia).",
        "thresholds": "Cita el umbral y la lectura técnica que implica (cruce, agotamiento, ruptura de banda).",
        "ipsa": False,
        "max_words": 40,
        "forbidden_terms": (),
    },
}


def level_max_words(level: str) -> int:
    return LEVELS.get(level, LEVELS[DEFAULT_LEVEL])["max_words"]


def contains_forbidden_term(level: str, text: str) -> str | None:
    """Primer término prohibido del nivel presente en `text` (o None)."""
    lowered = text.lower()
    for term in LEVELS.get(level, LEVELS[DEFAULT_LEVEL])["forbidden_terms"]:
        if term in lowered:
            return term
    return None
