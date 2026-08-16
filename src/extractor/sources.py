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

PERIOD_TO_DAYS = {30: "1mo", 90: "3mo", 180: "6mo", 365: "1y"}

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


def fetch_batch_quotes(symbols: list, days: int = 5, max_retries: int = 2):
    """Obtiene precio actual y variacion diaria de varios instrumentos en un solo request.

    Usado por el sidebar del Presentador (RF-07.2) para listar el catalogo
    completo sin hacer una solicitud por instrumento. Si un simbolo no
    aparece en la respuesta del proveedor, queda en `None` en vez de
    interrumpir a los demas (tolerancia a fallos, RNF-08).

    Retorna: {symbol: {"price": float, "daily_change_pct": float} | None}
    """
    quotes = {sym: None for sym in symbols}
    if not symbols:
        return quotes

    def _download():
        return yf.download(
            tickers=list(symbols),
            period=f"{days}d",
            group_by="ticker",
            progress=False,
            threads=True,
            auto_adjust=True,
        )

    try:
        data = _retry(_download, max_retries)
    except DataSourceError:
        return quotes

    is_multi = hasattr(data, "columns") and isinstance(data.columns, pd.MultiIndex)

    for sym in symbols:
        try:
            if is_multi:
                if sym not in data.columns.get_level_values(0):
                    continue
                closes = data[sym]["Close"].dropna()
            elif len(symbols) == 1:
                closes = data["Close"].dropna()
            else:
                continue

            if closes.empty:
                continue

            last = float(closes.iloc[-1])
            prev = float(closes.iloc[-2]) if len(closes) >= 2 else last
            change_pct = ((last - prev) / prev * 100) if prev else 0.0
            quotes[sym] = {"price": round(last, 2), "daily_change_pct": round(change_pct, 2)}
        except Exception:  # noqa: BLE001 - un simbolo con datos malformados no debe romper el lote
            continue

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
