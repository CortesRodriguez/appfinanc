"""Modulo Procesador NLP (Sprint 6).

Transforma los `IndicadorNormalizado` producidos por el Extractor en
explicaciones comprensibles para inversionistas principiantes, y les
adjunta una clasificacion de riesgo. Cubre RF-04, RF-05 y RF-06.
"""

from .finbert import FinBertProcessor, ResultadoFinBert
from .validator import validar_coherencia, CoherenciaError, categoria_rsi
from .generator import GeneradorExplicaciones, Explicacion, PerfilAprendizaje
from .risk import clasificar_riesgo, NivelRiesgo
from .glosario import GLOSARIO, buscar_termino

__all__ = [
    "FinBertProcessor",
    "ResultadoFinBert",
    "validar_coherencia",
    "CoherenciaError",
    "categoria_rsi",
    "GeneradorExplicaciones",
    "Explicacion",
    "PerfilAprendizaje",
    "clasificar_riesgo",
    "NivelRiesgo",
    "GLOSARIO",
    "buscar_termino",
]
