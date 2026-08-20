"""Constantes compartidas entre modulos del Presentador (evita imports circulares)."""

INDICATOR_LABELS = {
    "rsi": "Índice de Fuerza Relativa (RSI)",
    "medias_moviles": "Tendencia por medias móviles",
    "macd": "Convergencia/Divergencia de Medias Móviles (MACD)",
    "bandas_bollinger": "Bandas de Bollinger",
}

# Umbral de activación del Instrumento 1 (Autoevaluación Retrospectiva).
# La encuesta se le ofrece a una persona registrada una vez que ha realizado
# al menos SURVEY_THRESHOLD consultas (contadas como `InstrumentVisit`).
# Antes de ese punto no hay exposición suficiente al sistema como para que la
# auto-percepción retrospectiva de "antes/ahora" sea informativa.
SURVEY_THRESHOLD = 5

# Escala de la autoevaluación retrospectiva (1 = nada, 5 = muy bien).
SURVEY_SCALE_MIN = 1
SURVEY_SCALE_MAX = 5
