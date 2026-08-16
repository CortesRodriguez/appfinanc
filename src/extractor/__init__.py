"""Modulo Extractor (RF-01, RF-02, RF-03).

Orquesta la seleccion de instrumento/periodo, la extraccion de datos
(con cache y reintentos), la normalizacion y el calculo de indicadores.
"""

from .cache import TTLCache, price_history_cache
from .indicators import INDICATOR_TYPES, compute_indicator, compute_ma_series
from .sources import DataSourceError, fetch_batch_quotes, fetch_macro_indicators, fetch_price_history

VALID_PERIODS = (30, 90, 180, 365)

quotes_cache = TTLCache(ttl_seconds=300)
macro_cache = TTLCache(ttl_seconds=300)


class ExtractionError(Exception):
    """Error de negocio expuesto al Presentador (RF-09.1)."""


def _validate_inputs(days: int, indicator: str = None):
    if days not in VALID_PERIODS:
        raise ExtractionError(f"Rango temporal invalido: {days}. Valores permitidos: {VALID_PERIODS}")
    if indicator is not None and indicator not in INDICATOR_TYPES:
        raise ExtractionError(f"Indicador invalido: {indicator}")


def _get_history(symbol: str, days: int, alpha_vantage_key: str, cache_ttl_seconds: int):
    cache_key = (symbol, days)
    price_history_cache.ttl_seconds = cache_ttl_seconds
    history = price_history_cache.get(cache_key)

    if history is None:
        try:
            history = fetch_price_history(symbol, days, alpha_vantage_key=alpha_vantage_key)
        except DataSourceError as exc:
            raise ExtractionError(
                "No fue posible obtener datos del instrumento seleccionado. "
                "Intenta nuevamente en unos minutos."
            ) from exc
        price_history_cache.set(cache_key, history)

    if not history["records"]:
        raise ExtractionError("No hay datos disponibles para el instrumento seleccionado.")

    return history


def get_indicator(symbol: str, indicator: str, days: int = 90, alpha_vantage_key: str = "", cache_ttl_seconds: int = 300):
    """Extrae el historial de precios (con cache RNF-02.2) y calcula el indicador solicitado.

    Retorna un dict con el valor del indicador, su nivel de riesgo, la
    fuente de datos utilizada y la marca de tiempo de extraccion
    (trazabilidad RF-02.2).
    """
    _validate_inputs(days, indicator)
    history = _get_history(symbol, days, alpha_vantage_key, cache_ttl_seconds)

    try:
        result = compute_indicator(indicator, history["records"])
    except ValueError as exc:
        raise ExtractionError(str(exc)) from exc

    result.update(
        {
            "symbol": symbol,
            "source": history["source"],
            "extracted_at": history["fetched_at"],
            "period_days": days,
        }
    )
    return result


def get_price_series(symbol: str, days: int = 365, alpha_vantage_key: str = "", cache_ttl_seconds: int = 300):
    """Serie de precios + medias moviles 50/200 para el grafico de tendencia (vista de escenarios)."""
    _validate_inputs(days)
    history = _get_history(symbol, days, alpha_vantage_key, cache_ttl_seconds)

    try:
        series = compute_ma_series(history["records"])
    except ValueError as exc:
        raise ExtractionError(str(exc)) from exc

    series.update({"symbol": symbol, "source": history["source"], "extracted_at": history["fetched_at"]})
    return series


def get_quotes(symbols: list, cache_ttl_seconds: int = 300):
    """Cotizaciones (precio + variacion diaria) para el listado del sidebar, cacheadas por lote."""
    cache_key = tuple(sorted(symbols))
    quotes_cache.ttl_seconds = cache_ttl_seconds
    cached = quotes_cache.get(cache_key)
    if cached is not None:
        return cached

    quotes = fetch_batch_quotes(symbols)
    quotes_cache.set(cache_key, quotes)
    return quotes


def get_macro_indicators(cache_ttl_seconds: int = 300):
    """UF, dolar, TPM e IPC (mindicador.cl), cacheados igual que las cotizaciones."""
    macro_cache.ttl_seconds = cache_ttl_seconds
    cached = macro_cache.get("macro")
    if cached is not None:
        return cached

    data = fetch_macro_indicators()
    macro_cache.set("macro", data)
    return data
