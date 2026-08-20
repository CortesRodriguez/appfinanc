"""Modulo Extractor (RF-01, RF-02, RF-03).

Orquesta la seleccion de instrumento/periodo, la extraccion de datos
(con cache y reintentos), la normalizacion y el calculo de indicadores.
"""

from .cache import TTLCache, price_history_cache
from .indicators import INDICATOR_TYPES, compute_indicator, compute_ma_series, resample_records
from .sources import DataSourceError, fetch_batch_quotes, fetch_macro_indicators, fetch_price_history

VALID_PERIODS = (30, 90, 180, 365)
VALID_INTERVALS = ("1d", "1w", "1mo", "3mo")

# Exploracion historica extendida: el grafico siempre trae MAX_CHART_FETCH_DAYS
# de historia (independiente del boton 1M/3M/6M/1A elegido) para que el usuario
# pueda panear/zoom-out al pasado hasta ese tope sin importar el rango inicial.
# La vista inicial se ancla a `days` (lo que el boton pidio) via `visible_days`
# en la respuesta; el resto queda como buffer navegable. Verificado empiricamente
# que el endpoint diario de Yahoo entrega datos reales para .SN cuando el period
# solicitado es largo (>= 2y). El placeholder plano solo aparece en periodos
# cortos como 5d/1mo. Techo pragmatico: 10 anos (~2500 filas por ticker).
MAX_CHART_FETCH_DAYS = 3650

quotes_cache = TTLCache(ttl_seconds=300)
macro_cache = TTLCache(ttl_seconds=300)


class ExtractionError(Exception):
    """Error de negocio expuesto al Presentador (RF-09.1)."""


def _validate_inputs(days: int, indicator: str = None, interval: str = None):
    if days not in VALID_PERIODS:
        raise ExtractionError(f"Rango temporal invalido: {days}. Valores permitidos: {VALID_PERIODS}")
    if indicator is not None and indicator not in INDICATOR_TYPES:
        raise ExtractionError(f"Indicador invalido: {indicator}")
    if interval is not None and interval not in VALID_INTERVALS:
        raise ExtractionError(f"Intervalo invalido: {interval}. Valores permitidos: {VALID_INTERVALS}")


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


def get_price_series(
    symbol: str,
    days: int = 365,
    interval: str = "1d",
    alpha_vantage_key: str = "",
    cache_ttl_seconds: int = 300,
):
    """Serie de precios + medias moviles para el grafico de tendencia.

    - `days`: ventana temporal pedida por el usuario (1M/3M/6M/1A). El fetch
      real es `CHART_BUFFER_FACTOR * days` (topeado en `MAX_CHART_FETCH_DAYS`)
      para permitir pan al pasado.
    - `interval`: granularidad de la vela (1d/1w/1mo/3mo). El extractor
      siempre baja datos diarios; para intervalos mayores se re-muestrean
      server-side con `resample_records`. Esto mantiene un solo path de
      caching y aprovecha el fallback horario que arregla el bug de .SN.
    """
    _validate_inputs(days, interval=interval)
    fetch_days = MAX_CHART_FETCH_DAYS
    history = _get_history(symbol, fetch_days, alpha_vantage_key, cache_ttl_seconds)

    records = history["records"]
    if interval != "1d":
        records = resample_records(records, interval)

    try:
        series = compute_ma_series(records)
    except ValueError as exc:
        raise ExtractionError(str(exc)) from exc

    series.update(
        {
            "symbol": symbol,
            "source": history["source"],
            "extracted_at": history["fetched_at"],
            "visible_days": days,
            "fetched_days": fetch_days,
            "interval": interval,
        }
    )
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
