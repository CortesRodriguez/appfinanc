"""Fuentes de datos financieros del modulo Extractor.

Implementa RF-02.1 (extraccion desde Yahoo Finance / Alpha Vantage),
RF-02.2 (trazabilidad de fecha/hora/fuente), RF-03.3 (normalizacion a una
estructura interna comun independiente de la API de origen) y RNF-08
(tolerancia a fallos de conexion, con reintentos automaticos).
"""

import time
from datetime import datetime, timezone

import pandas as pd
import requests
import yfinance as yf

ALPHAVANTAGE_URL = "https://www.alphavantage.co/query"
MINDICADOR_URL = "https://mindicador.cl/api"

# Cubre tanto los valores exactos que pide el usuario (30/90/180/365) como el
# valor grande que pide get_price_series para el buffer del chart (3650 = 10a).
# Se traduce a un period de Yahoo que garantice al menos ese numero de dias;
# el recorte fino se hace en _fetch_yahoo con `cutoff` sobre el DataFrame.
PERIOD_TO_DAYS = {
    30: "1mo", 60: "3mo", 90: "3mo",
    180: "6mo", 360: "1y", 365: "1y",
    730: "2y", 1825: "5y", 3650: "10y",
}

# RF-02.1 / Tabla "Indicadores financieros nacionales de Chile" de la memoria:
# UF, dolar y TPM se obtienen de mindicador.cl (API publica gratuita basada
# en cifras del Banco Central de Chile), fuente independiente de Yahoo
# Finance/Alpha Vantage que ya cubren instrumentos transados en bolsa.
MACRO_INDICATOR_KEYS = {
    "uf": "UF",
    "dolar": "Dólar",
    "tpm": "TPM",
    "ipc": "IPC",
}


class DataSourceError(Exception):
    """Se produce cuando ninguna fuente de datos pudo entregar informacion."""


def _retry(fn, max_retries: int, *args, **kwargs):
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - se reintenta cualquier falla de red/API
            last_error = exc
            if attempt < max_retries:
                time.sleep(0.5 * attempt)
    raise DataSourceError(str(last_error)) from last_error


def _fetch_yahoo(symbol: str, days: int):
    yf_period = PERIOD_TO_DAYS.get(days, "6mo")
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period=yf_period)
    if hist is None or hist.empty:
        raise DataSourceError(f"Yahoo Finance no devolvio datos para {symbol}")

    # Recorte por calendario, no por numero de filas: el usuario pide "3 meses"
    # y espera exactamente los ultimos 3 meses de velas, tal como los muestra
    # Bolsa de Santiago. Contar filas de trading desalinea la ventana temporal.
    cutoff = pd.Timestamp.now(tz=hist.index.tz) - pd.Timedelta(days=days)
    hist = hist[hist.index >= cutoff]
    if hist.empty:
        raise DataSourceError(f"Yahoo Finance no devolvio datos recientes para {symbol}")

    # Yahoo a veces devuelve filas con Close=NaN (dia de trading en curso sin
    # cierre aun, feriado parcial, hueco en el ticker). Esos NaN se propagan a
    # traves de compute_rsi / compute_bollinger / etc. y terminan violando el
    # NOT NULL de coherence_checks.value en SQLite, provocando un 500 y un
    # response HTML que el frontend no puede parsear como JSON. Se descartan
    # aqui, en la fuente, antes que el resto del pipeline los vea.
    hist = hist.dropna(subset=["Close"])
    if hist.empty:
        raise DataSourceError(f"Yahoo Finance no devolvio precios validos para {symbol}")

    # Yahoo tambien devuelve filas "stale" al final del rango cuando el ticker
    # no se transo ese dia (Volume=0 pero Close = cierre del dia anterior). Si
    # esos dias entran al calculo del RSI, la ventana de 14 dias queda con
    # deltas = 0 al final, forzando rs = 0/NaN y un RSI congelado en 0 o 100
    # (valor de dias muy anteriores que sobrevive al dropna). El fix minimo es
    # recortar las filas trailing sin volumen; los dias intermedios sin volumen
    # se conservan para no reescribir la serie.
    while len(hist) > 1 and hist["Volume"].iloc[-1] == 0:
        hist = hist.iloc[:-1]
    if hist.empty:
        raise DataSourceError(f"Yahoo Finance no devolvio dias de trading recientes para {symbol}")

    # El endpoint diario de Yahoo devuelve un placeholder plano (OHLC iguales,
    # volumen 0) para varios .SN de la Bolsa de Santiago cuando se pide un
    # periodo corto (5d/1mo). Detectarlo y caer al endpoint horario re-muestreado
    # a diario, que si tiene los datos reales. El intraday esta limitado a 730d
    # por Yahoo — si nos pidieron mas, el fallback devuelve lo que pueda (hasta 2a).
    if hist["Volume"].sum() == 0 or hist["Close"].nunique() == 1:
        hourly_period = yf_period if days <= 730 else "2y"
        hourly = ticker.history(period=hourly_period, interval="1h")
        if hourly is None or hourly.empty:
            raise DataSourceError(f"Yahoo Finance no devolvio datos horarios para {symbol}")
        hourly = hourly[hourly.index >= cutoff]
        hist = (
            hourly.resample("D")
            .agg({"Open": "first", "High": "max", "Low": "min", "Close": "last"})
            .dropna()
        )
        if hist.empty:
            raise DataSourceError(f"Yahoo Finance no devolvio datos horarios recientes para {symbol}")

    records = [
        {
            "date": idx.strftime("%Y-%m-%d"),
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
        }
        for idx, row in hist.iterrows()
    ]
    return records


def _fetch_alpha_vantage(symbol: str, days: int, api_key: str):
    if not api_key:
        raise DataSourceError("No hay API key de Alpha Vantage configurada")

    # outputsize=compact devuelve solo 100 filas; para 1A (365 dias) queda corto.
    outputsize = "full" if days > 100 else "compact"
    params = {
        "function": "TIME_SERIES_DAILY",
        "symbol": symbol,
        "outputsize": outputsize,
        "apikey": api_key,
    }
    response = requests.get(ALPHAVANTAGE_URL, params=params, timeout=10)
    response.raise_for_status()
    payload = response.json()

    series = payload.get("Time Series (Daily)")
    if not series:
        raise DataSourceError(
            payload.get("Note") or payload.get("Error Message") or "Respuesta invalida de Alpha Vantage"
        )

    cutoff = (pd.Timestamp.now().normalize() - pd.Timedelta(days=days)).strftime("%Y-%m-%d")
    dates = sorted(d for d in series.keys() if d >= cutoff)
    if not dates:
        raise DataSourceError(f"Alpha Vantage no devolvio datos recientes para {symbol}")
    records = [
        {
            "date": d,
            "open": float(series[d]["1. open"]),
            "high": float(series[d]["2. high"]),
            "low": float(series[d]["3. low"]),
            "close": float(series[d]["4. close"]),
        }
        for d in dates
    ]
    return records


def fetch_price_history(symbol: str, days: int, alpha_vantage_key: str = "", max_retries: int = 3):
    """Obtiene el historial de precios de cierre, normalizado, con trazabilidad de fuente.

    Retorna un dict: {"symbol", "source", "fetched_at", "records": [{"date","close"}, ...]}
    """
    try:
        records = _retry(_fetch_yahoo, max_retries, symbol, days)
        source = "Yahoo Finance"
    except DataSourceError:
        records = _retry(_fetch_alpha_vantage, max_retries, symbol, days, alpha_vantage_key)
        source = "Alpha Vantage"

    return {
        "symbol": symbol,
        "source": source,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "records": records,
    }


def fetch_batch_quotes(symbols: list, max_retries: int = 2):
    """Obtiene precio actual y variacion diaria de varios instrumentos.

    Usado por el sidebar del Presentador (RF-07.2) para listar el catalogo
    completo. Consulta el endpoint `quoteSummary` de Yahoo por simbolo
    (via `Ticker.info`) porque el batch de velas diarias entrega un
    placeholder plano para muchos .SN de la Bolsa de Santiago. Si un
    simbolo falla, queda en `None` en vez de interrumpir a los demas
    (tolerancia a fallos, RNF-08).

    Retorna: {symbol: {"price": float, "daily_change_pct": float} | None}
    """
    quotes = {sym: None for sym in symbols}
    if not symbols:
        return quotes

    for sym in symbols:
        try:
            info = _retry(lambda s=sym: yf.Ticker(s).info, max_retries)
        except DataSourceError:
            continue

        if not isinstance(info, dict):
            continue

        price = info.get("regularMarketPrice") or info.get("currentPrice")
        prev = info.get("regularMarketPreviousClose") or info.get("previousClose")
        if price is None:
            continue

        try:
            price = float(price)
            prev = float(prev) if prev is not None else price
        except (TypeError, ValueError):
            continue

        change_pct = ((price - prev) / prev * 100) if prev else 0.0
        quotes[sym] = {"price": round(price, 2), "daily_change_pct": round(change_pct, 2)}

    return quotes


def fetch_macro_indicators(max_retries: int = 2):
    """Obtiene UF, dolar, TPM e IPC desde mindicador.cl (Banco Central de Chile).

    Retorna {clave: {"label", "value", "date"}}; si la API no responde,
    retorna un dict vacio en vez de propagar el error (RNF-08): estos
    indicadores son un complemento informativo de la cinta de precios,
    no deben tumbar el resto del dashboard si fallan.
    """

    def _fetch():
        response = requests.get(MINDICADOR_URL, timeout=8)
        response.raise_for_status()
        return response.json()

    try:
        data = _retry(_fetch, max_retries)
    except DataSourceError:
        return {}

    result = {}
    for key, label in MACRO_INDICATOR_KEYS.items():
        entry = data.get(key)
        if entry and "valor" in entry:
            result[key] = {"label": label, "value": entry["valor"], "date": entry.get("fecha")}

    return result
