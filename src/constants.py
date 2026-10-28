"""Constantes compartidas entre modulos del Presentador (evita imports circulares)."""

INDICATOR_LABELS = {
    "rsi": "Índice de Fuerza Relativa (RSI)",
    "medias_moviles": "Tendencia por medias móviles",
    "macd": "Convergencia/Divergencia de Medias Móviles (MACD)",
    "bandas_bollinger": "Bandas de Bollinger",
}

# Nombres cortos para espacios reducidos (perfil, chips).
INDICATOR_SHORT_LABELS = {
    "rsi": "RSI",
    "medias_moviles": "Medias móviles",
    "macd": "MACD",
    "bandas_bollinger": "Bandas de Bollinger",
}
