"""Calculo de indicadores tecnicos.

RF-02.1: volatilidad, RSI, medias moviles y rentabilidad.
Se calculan desde la serie de precios historicos entregada por
Yahoo Finance / Alpha Vantage. Los valores se dejan listos para ser
validados por `validator.py` y luego normalizados.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd


@dataclass
class IndicadoresTecnicos:
    """Resultado del calculo tecnico para un instrumento y rango."""

    ticker: str
    rango: str
    precio_actual: float
    volatilidad: float
    rsi: float
    media_movil_corta: float
    media_movil_larga: float
    rentabilidad: float

    def as_dict(self) -> dict[str, float | str]:
        return {
            "ticker": self.ticker,
            "rango": self.rango,
            "precio_actual": self.precio_actual,
            "volatilidad": self.volatilidad,
            "rsi": self.rsi,
            "media_movil_corta": self.media_movil_corta,
            "media_movil_larga": self.media_movil_larga,
            "rentabilidad": self.rentabilidad,
        }


def _volatilidad_anualizada(precios: pd.Series) -> float:
    retornos = precios.pct_change().dropna()
    if retornos.empty:
        return math.nan
    return float(retornos.std() * math.sqrt(252) * 100)


def _rsi(precios: pd.Series, ventana: int = 14) -> float:
    if len(precios) <= ventana:
        return math.nan
    delta = precios.diff().dropna()
    ganancias = delta.clip(lower=0.0)
    perdidas = -delta.clip(upper=0.0)
    media_ganancia = ganancias.rolling(ventana).mean().iloc[-1]
    media_perdida = perdidas.rolling(ventana).mean().iloc[-1]
    if media_perdida == 0:
        return 100.0
    rs = media_ganancia / media_perdida
    return float(100 - (100 / (1 + rs)))


def _media_movil(precios: pd.Series, ventana: int) -> float:
    if len(precios) < ventana:
        return math.nan
    return float(precios.rolling(ventana).mean().iloc[-1])


def _rentabilidad_pct(precios: pd.Series) -> float:
    if precios.empty:
        return math.nan
    inicial = precios.iloc[0]
    final = precios.iloc[-1]
    if inicial == 0:
        return math.nan
    return float(((final - inicial) / inicial) * 100)


def calcular_indicadores(
    df: pd.DataFrame,
    ticker: str,
    rango: str,
    columna_precio: str = "Close",
) -> IndicadoresTecnicos:
    """Calcula el set de indicadores requeridos por RF-02.1.

    Recibe un DataFrame con al menos la columna de precio de cierre
    diario y devuelve la estructura interna comun (RF-03.3).
    """

    if df.empty or columna_precio not in df.columns:
        raise ValueError(
            f"Serie de precios vacia o sin columna '{columna_precio}' para {ticker}."
        )

    precios = df[columna_precio].dropna().astype(float)

    return IndicadoresTecnicos(
        ticker=ticker,
        rango=rango,
        precio_actual=float(precios.iloc[-1]),
        volatilidad=_volatilidad_anualizada(precios),
        rsi=_rsi(precios),
        media_movil_corta=_media_movil(precios, ventana=20),
        media_movil_larga=_media_movil(precios, ventana=50),
        rentabilidad=_rentabilidad_pct(precios),
    )
