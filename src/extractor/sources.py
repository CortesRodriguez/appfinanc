"""Fuentes de datos financieros del modulo Extractor.

Implementa RF-02.1 (extraccion desde Yahoo Finance / Alpha Vantage),
RF-02.2 (trazabilidad de fecha/hora/fuente), RF-03.3 (normalizacion a una
estructura interna comun independiente de la API de origen) y RNF-08
(tolerancia a fallos de conexion, con reintentos automaticos).
"""

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urlparse

import pandas as pd
import requests
import yfinance as yf

ALPHAVANTAGE_URL = "https://www.alphavantage.co/query"
MINDICADOR_URL = "https://mindicador.cl/api"

# `period` de Yahoo que cubre cada rango pedido (30/90/180/365 por el usuario,
# 3650 por el buffer del grafico). Solo se usa en el fallback horario; la
# descarga diaria usa start/end y el recorte fino se hace con `cutoff`.
DAYS_TO_YAHOO_PERIOD = {30: "1mo", 90: "3mo", 180: "6mo", 365: "1y", 3650: "10y"}

# RF-02.1 / Tabla "Indicadores financieros nacionales de Chile" de la memoria:
# UF, dolar y TPM se obtienen de mindicador.cl (API publica gratuita basada
# en cifras del Banco Central de Chile), fuente independiente de Yahoo
# Finance/Alpha Vantage que ya cubren instrumentos transados en bolsa.
# Clave de la API -> etiqueta que ve el usuario.
MACRO_LABELS = {
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


def _require(df, message: str):
    """Devuelve `df` o lanza DataSourceError(message) si no tiene filas."""
    if df is None or df.empty:
        raise DataSourceError(message)
    return df


def _get_json(url: str, params: dict = None, timeout: int = 10):
    """GET + JSON para las APIs HTTP (Alpha Vantage, mindicador.cl).

    El mensaje de `requests` incluye la URL completa, y la de Alpha Vantage
    lleva `apikey=...`: se relanza sin ella para que no llegue a logs ni trazas.
    """
    try:
        response = requests.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        raise DataSourceError(f"{type(exc).__name__} al consultar {urlparse(url).netloc}") from None


def _to_records(df):
    """Normaliza un DataFrame OHLC (indice = fecha) a la lista de dicts comun (RF-03.3)."""
    return [
        {
            "date": idx.strftime("%Y-%m-%d"),
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
        }
        for idx, row in df.iterrows()
    ]


def _drop_open_session(hist):
    """Quita la fila de HOY si tiene Volume=0 (sesion en curso sin cierre).

    Dias historicos con Volume=0 se conservan: son dias sin transaccion pero
    con precio valido y deben visualizarse como velas planas en el grafico.
    """
    today = pd.Timestamp.now().strftime("%Y-%m-%d")
    if len(hist) > 1 and hist["Volume"].iloc[-1] == 0 and hist.index[-1].strftime("%Y-%m-%d") == today:
        return hist.iloc[:-1]
    return hist


def _stale_flags(hist):
    """Detecta datos obsoletos del endpoint diario de Yahoo para tickers .SN (Bolsa de Santiago).

    Devuelve (all_bad, recent_stale):
      all_bad:      todos los datos son placeholder (sum Volume=0 o Close unico).
      recent_stale: el historico antiguo es valido pero la cola reciente tiene
                    Volume=0 y Close constante: Yahoo sirve un placeholder plano
                    para las ultimas semanas sin tocar el historial anterior.
    """
    tail_n = min(15, len(hist))
    recent_stale = (
        tail_n >= 5
        and hist["Volume"].iloc[-tail_n:].sum() == 0
        and hist["Close"].iloc[-tail_n:].nunique() == 1
    )
    all_bad = hist["Volume"].sum() == 0 or hist["Close"].nunique() == 1
    return all_bad, recent_stale


def _hourly_as_daily(ticker, symbol: str, days: int, cutoff):
    """Velas diarias reconstruidas desde el intraday horario, que si trae precios reales.

    Limite de Yahoo: 730d horarios; para requests mas largos pide "2y" (lo que pueda).
    """
    period = DAYS_TO_YAHOO_PERIOD.get(days, "6mo") if days <= 730 else "2y"
    hourly = _require(
        ticker.history(period=period, interval="1h"),
        f"Yahoo Finance no devolvio datos horarios para {symbol}",
    )
    daily = (
        hourly[hourly.index >= cutoff]
        .resample("D")
        .agg({"Open": "first", "High": "max", "Low": "min", "Close": "last"})
        .dropna()
    )
    return _require(daily, f"Yahoo Finance no devolvio datos horarios recientes para {symbol}")


def _replace_stale_tail(hist, hourly_daily):
    """Conserva el historial diario real y reemplaza solo la cola obsoleta con datos horarios.

    Esto preserva el buffer de 10 anos del grafico principal.
    """
    real_mask = hist["Volume"] > 0
    if not real_mask.any():
        return hourly_daily
    last_real = hist[real_mask].index[-1]
    hist_real = hist.loc[hist.index <= last_real, ["Open", "High", "Low", "Close"]]
    merged = pd.concat([hist_real, hourly_daily[hourly_daily.index > last_real.normalize()]])
    return merged[~merged.index.duplicated(keep="last")].sort_index()


def _fetch_yahoo(symbol: str, days: int):
    ticker = yf.Ticker(symbol)
    now = pd.Timestamp.now()
    hist = _require(
        ticker.history(
            start=(now - pd.Timedelta(days=days)).strftime("%Y-%m-%d"),
            end=(now + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
        ),
        f"Yahoo Finance no devolvio datos para {symbol}",
    )

    # Recorte por calendario, no por numero de filas: el usuario pide "3 meses"
    # y espera exactamente los ultimos 3 meses de velas, tal como los muestra
    # Bolsa de Santiago. Contar filas de trading desalinea la ventana temporal.
    cutoff = pd.Timestamp.now(tz=hist.index.tz) - pd.Timedelta(days=days)
    hist = _require(hist[hist.index >= cutoff], f"Yahoo Finance no devolvio datos recientes para {symbol}")

    # Yahoo a veces devuelve filas con Close=NaN (dia de trading en curso sin
    # cierre aun, feriado parcial, hueco en el ticker). Esos NaN se propagan a
    # traves de compute_rsi / compute_bollinger / etc. y terminan en un 500 con
    # response HTML que el frontend no puede parsear como JSON. Se descartan
    # aqui, en la fuente, antes que el resto del pipeline los vea.
    hist = _require(hist.dropna(subset=["Close"]), f"Yahoo Finance no devolvio precios validos para {symbol}")
    hist = _require(_drop_open_session(hist), f"Yahoo Finance no devolvio dias de trading recientes para {symbol}")

    all_bad, recent_stale = _stale_flags(hist)
    if all_bad or recent_stale:
        hourly_daily = _hourly_as_daily(ticker, symbol, days, cutoff)
        hist = hourly_daily if all_bad else _replace_stale_tail(hist, hourly_daily)
        _require(hist, f"Yahoo Finance no devolvio datos recientes para {symbol}")

    return _to_records(hist)


def _fetch_alpha_vantage(symbol: str, days: int, api_key: str):
    if not api_key:
        raise DataSourceError("No hay API key de Alpha Vantage configurada")

    payload = _get_json(
        ALPHAVANTAGE_URL,
        params={
            "function": "TIME_SERIES_DAILY",
            "symbol": symbol,
            # outputsize=compact devuelve solo 100 filas; para 1A (365 dias) queda corto.
            "outputsize": "full" if days > 100 else "compact",
            "apikey": api_key,
        },
    )
    series = payload.get("Time Series (Daily)")
    if not series:
        raise DataSourceError(
            payload.get("Note")
            or payload.get("Information")
            or payload.get("Error Message")
            or "Respuesta invalida de Alpha Vantage"
        )

    df = pd.DataFrame.from_dict(series, orient="index").astype(float)
    df.columns = ["Open", "High", "Low", "Close"]  # "1. open", "2. high", "3. low", "4. close"
    df.index = pd.to_datetime(df.index)
    cutoff = pd.Timestamp.now().normalize() - pd.Timedelta(days=days)
    df = _require(df.sort_index()[lambda d: d.index >= cutoff], f"Alpha Vantage no devolvio datos recientes para {symbol}")
    return _to_records(df)


def fetch_price_history(symbol: str, days: int, alpha_vantage_key: str = "", max_retries: int = 3):
    """Obtiene el historial de precios OHLC, normalizado, con trazabilidad de fuente.

    Retorna un dict: {"symbol", "source", "fetched_at", "records": [{"date","open","high","low","close"}, ...]}
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


def _quote_for(symbol: str):
    """{"price", "daily_change_pct"} de un instrumento, o None si Yahoo no lo entrega."""
    try:
        info = yf.Ticker(symbol).info
        if not isinstance(info, dict):
            return None
        price = info.get("regularMarketPrice") or info.get("currentPrice")
        prev = info.get("regularMarketPreviousClose") or info.get("previousClose")
        if price is None:
            return None
        price = float(price)
        prev = float(prev) if prev is not None else price
        change = (price - prev) / prev * 100 if prev else 0.0
        return {"price": round(price, 2), "daily_change_pct": round(change, 2)}
    except Exception:  # noqa: BLE001 - simbolo faltante no interrumpe el resto (RNF-08)
        return None


def fetch_batch_quotes(symbols: list):
    """Obtiene precio actual y variacion diaria de varios instrumentos.

    Consulta cada ticker en paralelo (ThreadPoolExecutor) en lugar de usar
    yf.download, ya que el endpoint diario de Yahoo Finance devuelve datos
    obsoletos para tickers .SN de la Bolsa de Santiago (Volume=0, Close
    constante). `Ticker.info` entrega el precio en tiempo real y el cierre
    anterior directamente desde la API de quotes de Yahoo, evitando el problema.

    Retorna: {symbol: {"price": float, "daily_change_pct": float} | None}
    """
    if not symbols:
        return {}
    with ThreadPoolExecutor(max_workers=min(10, len(symbols))) as executor:
        return dict(zip(symbols, executor.map(_quote_for, symbols)))


def fetch_macro_indicators(max_retries: int = 2):
    """Obtiene UF, dolar, TPM e IPC desde mindicador.cl (Banco Central de Chile).

    Retorna {clave: {"label", "value", "date"}}; si la API no responde,
    retorna un dict vacio en vez de propagar el error (RNF-08): estos
    indicadores son un complemento informativo de la cinta de precios,
    no deben tumbar el resto del dashboard si fallan.
    """
    try:
        data = _retry(_get_json, max_retries, MINDICADOR_URL, timeout=8)
    except DataSourceError:
        return {}

    return {
        key: {"label": label, "value": data[key]["valor"], "date": data[key].get("fecha")}
        for key, label in MACRO_LABELS.items()
        if data.get(key) and "valor" in data[key]
    }
