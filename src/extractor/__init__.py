"""Modulo Extractor (RF-01, RF-02, RF-03).

Orquesta la seleccion de instrumento/periodo, la extraccion de datos
(con cache y reintentos), la normalizacion y el calculo de indicadores.
"""

from .cache import TTLCache, price_history_cache
from .news import get_company_news, get_market_news
from .indicators import INDICATOR_TYPES, compute_indicator, compute_ma_series, resample_records
from .sources import DataSourceError, fetch_batch_quotes, fetch_macro_indicators, fetch_price_history

VALID_PERIODS = (30, 90, 180, 365)
VALID_INTERVALS = ("1d", "1w", "1mo", "3mo")
# Igual al largo de `instrument` en query_logs / instrument_visits: PostgreSQL
# rechaza valores mas largos que el VARCHAR, asi que se corta aca con un 4xx
# en vez de dejar que llegue a la base como un 500.
MAX_SYMBOL_LENGTH = 20

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


def _validate_inputs(days: int, indicator: str = None, interval: str = None, symbol: str = None):
    if symbol is not None and not 0 < len(symbol) <= MAX_SYMBOL_LENGTH:
        raise ExtractionError(f"Ticker invalido: debe tener entre 1 y {MAX_SYMBOL_LENGTH} caracteres.")
    if days not in VALID_PERIODS:
        raise ExtractionError(f"Rango temporal invalido: {days}. Valores permitidos: {VALID_PERIODS}")
    if indicator is not None and indicator not in INDICATOR_TYPES:
        raise ExtractionError(f"Indicador invalido: {indicator}")
    if interval is not None and interval not in VALID_INTERVALS:
        raise ExtractionError(f"Intervalo invalido: {interval}. Valores permitidos: {VALID_INTERVALS}")


def _get_history(symbol: str, alpha_vantage_key: str, cache_ttl_seconds: int):
    """Historial completo (MAX_CHART_FETCH_DAYS) de `symbol`, descargado y cacheado una vez.

    Grafico y tarjetas leen la misma descarga: pedir una por cada rango
    multiplicaba las llamadas a Yahoo por instrumento.
    """
    def load():
        try:
            return fetch_price_history(symbol, MAX_CHART_FETCH_DAYS, alpha_vantage_key=alpha_vantage_key)
        except DataSourceError as exc:
            raise ExtractionError(
                "No fue posible obtener datos del instrumento seleccionado. "
                "Intenta nuevamente en unos minutos."
            ) from exc

    history = price_history_cache.get_or_load(symbol, load, cache_ttl_seconds)
    if not history["records"]:
        raise ExtractionError("No hay datos disponibles para el instrumento seleccionado.")

    return history


def _compute(fn, *args):
    """Ejecuta un calculo de indicadores convirtiendo su ValueError en error de negocio."""
    try:
        return fn(*args)
    except ValueError as exc:
        raise ExtractionError(str(exc)) from exc


def _trace(history: dict):
    """Trazabilidad RF-02.2: de que fuente y cuando salieron los datos."""
    return {"source": history["source"], "extracted_at": history["fetched_at"]}


def get_indicator(symbol: str, indicator: str, days: int = 90, alpha_vantage_key: str = "", cache_ttl_seconds: int = 300):
    """Extrae el historial de precios (con cache RNF-02.2) y calcula el indicador solicitado.

    El indicador se calcula sobre todo el historial disponible, no solo sobre
    `days`: RSI, MACD y medias moviles son indicadores definidos sobre una
    historia larga (EMA/Wilder arrastran todo el pasado) y recortar la entrada
    los distorsiona o, con 1M, impide calcular MACD. Asi coinciden con los del
    grafico. `days` solo identifica el periodo elegido (period_days, historial).

    Retorna un dict con el valor del indicador, su nivel de riesgo, la
    fuente de datos utilizada y la marca de tiempo de extraccion
    (trazabilidad RF-02.2).
    """
    _validate_inputs(days, indicator, symbol=symbol)
    history = _get_history(symbol, alpha_vantage_key, cache_ttl_seconds)

    result = _compute(compute_indicator, indicator, history["records"])
    result.update({"symbol": symbol, **_trace(history), "period_days": days})
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
      real es siempre `MAX_CHART_FETCH_DAYS` para permitir pan al pasado;
      `days` solo se devuelve como `visible_days` para anclar la vista inicial.
    - `interval`: granularidad de la vela (1d/1w/1mo/3mo). El extractor
      siempre baja datos diarios; para intervalos mayores se re-muestrean
      server-side con `resample_records`. Esto mantiene un solo path de
      caching y aprovecha el fallback horario que arregla el bug de .SN.
    """
    _validate_inputs(days, interval=interval, symbol=symbol)
    fetch_days = MAX_CHART_FETCH_DAYS
    history = _get_history(symbol, alpha_vantage_key, cache_ttl_seconds)

    records = history["records"]
    if interval != "1d":
        records = resample_records(records, interval)

    series = _compute(compute_ma_series, records)
    series.update(
        {
            "symbol": symbol,
            **_trace(history),
            "visible_days": days,
            "fetched_days": fetch_days,
            "interval": interval,
        }
    )
    return series


def get_quotes(symbols: list, cache_ttl_seconds: int = 300):
    """Cotizaciones (precio + variacion diaria) para el listado del sidebar, cacheadas por lote.

    Un lote donde todo fallo no se cachea: la proxima carga reintenta en vez de
    mostrar el sidebar vacio hasta que venza el TTL.
    """
    return quotes_cache.get_or_load(
        tuple(sorted(symbols)),
        lambda: fetch_batch_quotes(symbols),
        cache_ttl_seconds,
        cacheable=lambda quotes: any(quotes.values()),
    )


def get_macro_indicators(cache_ttl_seconds: int = 300):
    """UF, dolar, TPM e IPC (mindicador.cl), cacheados igual que las cotizaciones."""
    return macro_cache.get_or_load("macro", fetch_macro_indicators, cache_ttl_seconds, cacheable=bool)
