"""Extractor alternativo desde Alpha Vantage.

RF-02.1 menciona Yahoo Finance API o Alpha Vantage. Este modulo
mantiene la simetria con `YahooExtractor` para que el resto del sistema
pueda intercambiar la fuente sin cambios en interfaces.

La API key se lee desde la variable de entorno ALPHA_VANTAGE_API_KEY.
Si no esta definida, el extractor lanza una excepcion clara y deja
al orquestador caer de vuelta a Yahoo Finance.
"""

from __future__ import annotations

import logging
import os

import pandas as pd
import requests

from .cache import CacheIndicadores, con_reintentos
from .config import IPSA_TICKERS, RANGOS_TEMPORALES
from .indicators import IndicadoresTecnicos, calcular_indicadores
from .normalizer import IndicadorNormalizado, normalizar_indicador
from .traceability import Trazabilidad

_LOG = logging.getLogger("extractor.alpha_vantage")
_ENDPOINT = "https://www.alphavantage.co/query"
# Alpha Vantage devuelve serie diaria completa; se recorta a los ultimos
# N puntos segun el rango temporal solicitado.
_PUNTOS_POR_RANGO = {"1mo": 22, "3mo": 66, "6mo": 132, "1y": 252}


class AlphaVantageNoConfiguradoError(RuntimeError):
    """No hay ALPHA_VANTAGE_API_KEY definida en el entorno."""


class AlphaVantageExtractor:
    """Extractor de fallback. Interfaz identica a `YahooExtractor`."""

    FUENTE = "Alpha Vantage"

    def __init__(
        self,
        api_key: str | None = None,
        cache: CacheIndicadores | None = None,
        trazabilidad: Trazabilidad | None = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("ALPHA_VANTAGE_API_KEY")
        self.cache = cache or CacheIndicadores()
        self.trazabilidad = trazabilidad or Trazabilidad()

    def extraer(self, ticker: str, rango: str) -> IndicadorNormalizado:
        if not self.api_key:
            raise AlphaVantageNoConfiguradoError(
                "ALPHA_VANTAGE_API_KEY no definida; imposible usar Alpha Vantage."
            )
        if ticker not in IPSA_TICKERS:
            raise ValueError(
                f"Ticker '{ticker}' no pertenece al listado del IPSA (RF-01.1)."
            )
        if rango not in RANGOS_TEMPORALES:
            raise ValueError(
                f"Rango '{rango}' no soportado. Usar uno de "
                f"{list(RANGOS_TEMPORALES)}."
            )

        clave = f"av::{ticker}::{rango}"
        cacheado = self.cache.get(clave)
        if cacheado is not None:
            _LOG.info("cache hit alpha vantage para %s %s", ticker, rango)
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

    def _descargar_precios(self, ticker: str, rango: str) -> pd.DataFrame:
        params = {
            "function": "TIME_SERIES_DAILY",
            "symbol": ticker,
            "outputsize": "full",
            "apikey": self.api_key,
        }
        respuesta = requests.get(_ENDPOINT, params=params, timeout=15)
        respuesta.raise_for_status()
        payload = respuesta.json()

        serie = payload.get("Time Series (Daily)")
        if not serie:
            mensaje = payload.get("Note") or payload.get("Error Message") or (
                "Alpha Vantage no devolvio la serie diaria esperada."
            )
            raise RuntimeError(mensaje)

        df = pd.DataFrame.from_dict(serie, orient="index").sort_index()
        df.rename(
            columns={
                "1. open": "Open",
                "2. high": "High",
                "3. low": "Low",
                "4. close": "Close",
                "5. volume": "Volume",
            },
            inplace=True,
        )
        df["Close"] = df["Close"].astype(float)
        puntos = _PUNTOS_POR_RANGO[RANGOS_TEMPORALES[rango]]
        return df.tail(puntos)

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
