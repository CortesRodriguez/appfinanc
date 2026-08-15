"""Normalizacion a una estructura de datos interna comun.

RF-03.3: independientemente de la API de origen, los indicadores se
entregan al Procesador NLP en un formato uniforme. Esta clase es el
contrato que consumira el Sprint 6.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from .indicators import IndicadoresTecnicos
from .validator import validar_indicador


@dataclass
class IndicadorNormalizado:
    """Contrato de datos comun entre el Extractor y el Procesador NLP."""

    ticker: str
    rango: str
    fuente: str
    fecha_extraccion: str
    precio_actual: float
    volatilidad: float
    rsi: float
    media_movil_corta: float
    media_movil_larga: float
    rentabilidad: float
    metadata: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)


def normalizar_indicador(
    indicadores: IndicadoresTecnicos,
    fuente: str,
    metadata: dict[str, str] | None = None,
) -> IndicadorNormalizado:
    """Valida (RF-03.2) y normaliza (RF-03.3) el bundle de indicadores."""

    campos_validados = {
        "precio_actual": validar_indicador("precio", indicadores.precio_actual),
        "volatilidad": validar_indicador("volatilidad", indicadores.volatilidad),
        "rsi": validar_indicador("rsi", indicadores.rsi),
        "media_movil_corta": validar_indicador("media_movil", indicadores.media_movil_corta),
        "media_movil_larga": validar_indicador("media_movil", indicadores.media_movil_larga),
        "rentabilidad": validar_indicador("rentabilidad", indicadores.rentabilidad),
    }

    return IndicadorNormalizado(
        ticker=indicadores.ticker,
        rango=indicadores.rango,
        fuente=fuente,
        fecha_extraccion=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        metadata=metadata or {},
        **campos_validados,
    )
