"""Modulo Extractor del sistema (Sprint 5).

Obtiene, valida y normaliza los indicadores financieros que
alimentaran al Procesador NLP en sprints posteriores.
Cubre RF-01, RF-02 y RF-03 del anteproyecto.
"""

from .config import IPSA_TICKERS, RANGOS_TEMPORALES, RANGOS_VALIDOS
from .indicators import calcular_indicadores
from .yahoo_extractor import YahooExtractor
from .alpha_vantage_extractor import AlphaVantageExtractor
from .banco_central_extractor import BancoCentralExtractor
from .validator import validar_indicador
from .normalizer import normalizar_indicador, IndicadorNormalizado
from .cache import CacheIndicadores
from .traceability import Trazabilidad

__all__ = [
    "IPSA_TICKERS",
    "RANGOS_TEMPORALES",
    "RANGOS_VALIDOS",
    "calcular_indicadores",
    "YahooExtractor",
    "AlphaVantageExtractor",
    "BancoCentralExtractor",
    "validar_indicador",
    "normalizar_indicador",
    "IndicadorNormalizado",
    "CacheIndicadores",
    "Trazabilidad",
]
