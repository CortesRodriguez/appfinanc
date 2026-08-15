"""Extraccion de datos desde Yahoo Finance.

RF-02.1: obtiene el historial de precios de una empresa del IPSA para
un rango temporal dado y produce el bundle de indicadores
(volatilidad, RSI, medias moviles y rentabilidad).
"""

from __future__ import annotations

import logging

import pandas as pd
import yfinance as yf

from .cache import CacheIndicadores, con_reintentos
from .config import IPSA_TICKERS, RANGOS_TEMPORALES
from .indicators import IndicadoresTecnicos, calcular_indicadores
from .normalizer import IndicadorNormalizado, normalizar_indicador
from .traceability import Trazabilidad

_LOG = logging.getLogger("extractor.yahoo")


class InstrumentoNoSoportadoError(ValueError):
    """El ticker solicitado no pertenece al IPSA definido en config.py."""


class RangoNoSoportadoError(ValueError):
    """El rango temporal solicitado no es uno de los aceptados por RF-01.1."""


class YahooExtractor:
    """Extractor primario. Devuelve un `IndicadorNormalizado` listo para NLP."""

    FUENTE = "Yahoo Finance"

    def __init__(
        self,
        cache: CacheIndicadores | None = None,
        trazabilidad: Trazabilidad | None = None,
    ) -> None:
        self.cache = cache or CacheIndicadores()
        self.trazabilidad = trazabilidad or Trazabilidad()

    # ------------------------------------------------------------------
    # API publica
    # ------------------------------------------------------------------
    def extraer(self, ticker: str, rango: str) -> IndicadorNormalizado:
        """Extrae y normaliza los indicadores para un instrumento y rango."""

        self._validar_seleccion(ticker, rango)
        clave = f"yf::{ticker}::{rango}"

        cacheado = self.cache.get(clave)
        if cacheado is not None:
            _LOG.info("cache hit para %s %s", ticker, rango)
            return cacheado

        precios = con_reintentos(lambda: self._descargar_precios(ticker, rango))
        indicadores = calcular_indicadores(precios, ticker=ticker, rango=rango)
        normalizado = normalizar_indicador(
            indicadores,
            fuente=self.FUENTE,
            metadata={
                "nombre_empresa": IPSA_TICKERS[ticker],
                "filas_precio": str(len(precios)),
            },
        )
        self.cache.set(clave, normalizado)
        self._registrar(indicadores)
        return normalizado

    # ------------------------------------------------------------------
    # Helpers privados
    # ------------------------------------------------------------------
    def _validar_seleccion(self, ticker: str, rango: str) -> None:
        if ticker not in IPSA_TICKERS:
            raise InstrumentoNoSoportadoError(
                f"Ticker '{ticker}' no pertenece al listado del IPSA (RF-01.1)."
            )
        if rango not in RANGOS_TEMPORALES:
            raise RangoNoSoportadoError(
                f"Rango '{rango}' no soportado. Usar uno de "
                f"{list(RANGOS_TEMPORALES)}."
            )

    def _descargar_precios(self, ticker: str, rango: str) -> pd.DataFrame:
        periodo = RANGOS_TEMPORALES[rango]
        df = yf.download(
            ticker,
            period=periodo,
            interval="1d",
            progress=False,
            auto_adjust=True,
            threads=False,
        )
        if df is None or df.empty:
            raise RuntimeError(
                f"Yahoo Finance no devolvio datos para {ticker} ({rango})."
            )
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]
        return df

    def _registrar(self, indicadores: IndicadoresTecnicos) -> None:
        for nombre, valor in {
            "precio": indicadores.precio_actual,
            "volatilidad": indicadores.volatilidad,
            "rsi": indicadores.rsi,
            "media_movil_corta": indicadores.media_movil_corta,
            "media_movil_larga": indicadores.media_movil_larga,
            "rentabilidad": indicadores.rentabilidad,
        }.items():
            self.trazabilidad.registrar(
                ticker=indicadores.ticker,
                indicador=nombre,
                fuente=self.FUENTE,
                valor=valor,
            )
