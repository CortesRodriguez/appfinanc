"""Calculo de indicadores financieros y clasificacion de riesgo.

Implementa RF-02.1 (RSI, medias moviles, MACD, Bandas de Bollinger) y
RF-06.1 (clasificacion del nivel de riesgo relativo en bajo/medio/alto).

Los umbrales cualitativos usados aqui son los reglamentados en RF-04.2:
    RSI:    sobrecomprado si > 70, sobrevendido si < 30
    %B:     sobrecomprado si > 1, sobrevendido si < 0
    MACD:   alcista si linea MACD > linea de senal, bajista contrario
    MAs:    alcista si MA corta > MA larga, bajista contrario

Estos mismos umbrales alimentan al validador de coherencia semantica
(RF-04.2 / RF-13) para asegurar que el texto generado no contradiga al
dato numerico real.
"""

import numpy as np
import pandas as pd

# Se deriva de INDICATOR_FUNCTIONS (al final del modulo) para mantener una sola lista.

# Regla de re-muestreo de pandas para cada intervalo del selector de vela.
# "W" = semanal terminando en domingo; "MS" = inicio de mes; "QS" = inicio de
# trimestre. La agregacion OHLC es la estandar de finanzas (open=first,
# high=max, low=min, close=last).
_INTERVAL_TO_RULE = {"1w": "W", "1mo": "MS", "3mo": "QS"}


def _to_frame(records):
    """DataFrame ordenado por fecha e indexado por `date` (base de todo el modulo)."""
    if not records:
        raise ValueError("No hay datos de precios")
    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date").sort_index()


def _to_series(records):
    # Descartar filas con close=NaN antes de operar: si se cuela un NaN, se
    # propaga por diff() y rolling().mean() y termina como value=NaN en el
    # dict del indicador.
    return _to_frame(records)["close"].dropna()


def resample_records(records, interval):
    """Agrega records diarios `{date, open, high, low, close}` a la granularidad pedida.

    Con interval="1d" retorna los records tal cual (no hay agregacion). Para
    "1w"/"1mo"/"3mo" aplica pandas.resample con la regla OHLC estandar.
    """
    if interval not in _INTERVAL_TO_RULE:
        return records
    resampled = (
        _to_frame(records)
        .resample(_INTERVAL_TO_RULE[interval])
        .agg({"open": "first", "high": "max", "low": "min", "close": "last"})
        .dropna()
    )
    return [
        {
            "date": idx.strftime("%Y-%m-%d"),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
        }
        for idx, row in resampled.iterrows()
    ]


# Series completas de cada indicador. Cada compute_* toma su ultimo valor y
# compute_ma_series las entrega enteras al grafico, asi la formula vive una sola vez.

def _ma_windows(n_rows, short_window, long_window):
    """Ventanas de las medias moviles, reducidas si no hay historial suficiente."""
    return min(short_window, max(2, n_rows // 2)), min(long_window, n_rows)


def _rsi_series(close, window):
    """RSI de Wilder: suavizado exponencial de ganancias y perdidas."""
    delta = close.diff()
    avg_gain = delta.clip(lower=0).ewm(com=window - 1, adjust=False).mean()
    avg_loss = (-delta.clip(upper=0)).ewm(com=window - 1, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    # Sin perdidas en la ventana (solo subidas): RSI = 100 por definicion
    return rsi.where(~((avg_loss == 0) & (avg_gain > 0)), 100.0)


def _macd_series(close, fast=12, slow=26, signal_period=9):
    """(linea MACD, linea de senal, histograma)."""
    macd_line = close.ewm(span=fast, adjust=False).mean() - close.ewm(span=slow, adjust=False).mean()
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    return macd_line, signal_line, macd_line - signal_line


def _bollinger_series(close, window, num_std=2.0):
    """(banda media, superior, inferior)."""
    middle = close.rolling(window=window).mean()
    std = close.rolling(window=window).std()
    return middle, middle + num_std * std, middle - num_std * std


def compute_rsi(records, window: int = 14):
    """RSI de Wilder (14 dias). Umbrales oficiales: >70 sobrecomprado, <30 sobrevendido."""
    close = _to_series(records)
    if len(close) < window + 1:
        raise ValueError("No hay suficientes datos para calcular RSI")

    rsi_valid = _rsi_series(close, window).dropna()
    last_rsi = float(rsi_valid.iloc[-1]) if not rsi_valid.empty else 50.0

    # RF-04.2: categorias cualitativas segun umbrales oficiales
    if last_rsi > 70:
        signal = "sobrecomprado"
        risk = "alto"
    elif last_rsi < 30:
        signal = "sobrevendido"
        risk = "alto"
    else:
        signal = "neutral"
        risk = "medio" if 40 <= last_rsi <= 60 else "bajo"

    return {
        "indicator": "rsi",
        "value": round(last_rsi, 2),
        "unit": "pts",
        "risk_level": risk,
        "signal": signal,
    }


def compute_moving_averages(records, short_window: int = 50, long_window: int = 200):
    """Medias moviles. Umbral oficial: alcista si MA corta > MA larga."""
    close = _to_series(records)
    if len(close) < 5:
        raise ValueError("No hay suficientes datos para calcular medias moviles")

    short_window, long_window = _ma_windows(len(close), short_window, long_window)

    sma_short = close.rolling(window=short_window).mean().iloc[-1]
    sma_long = close.rolling(window=long_window).mean().iloc[-1]

    diff_pct = float((sma_short - sma_long) / sma_long * 100)
    trend = "alcista" if diff_pct > 0 else "bajista"
    # Diferencia pequena entre MAs = mercado sin direccion clara = riesgo medio.
    # Diferencia grande en cualquier direccion = movimiento pronunciado = riesgo alto.
    if abs(diff_pct) >= 10:
        risk = "alto"
    elif abs(diff_pct) < 3:
        risk = "medio"
    else:
        risk = "bajo"

    return {
        "indicator": "medias_moviles",
        "value": round(diff_pct, 2),
        "unit": "%",
        "risk_level": risk,
        "trend": trend,
        "sma_short": round(float(sma_short), 2),
        "sma_long": round(float(sma_long), 2),
    }


def compute_macd(records, fast: int = 12, slow: int = 26, signal_period: int = 9):
    """MACD estandar (12, 26, 9). Umbral oficial: alcista si linea MACD > linea de senal.

    - Linea MACD  = EMA(12) - EMA(26)
    - Linea senal = EMA(9) sobre la linea MACD
    - Histograma  = MACD - senal  (positivo = alcista)
    """
    close = _to_series(records)
    if len(close) < slow + signal_period:
        raise ValueError("No hay suficientes datos para calcular MACD")

    macd_line, signal_line, histogram = _macd_series(close, fast, slow, signal_period)

    last_macd = float(macd_line.iloc[-1])
    last_signal = float(signal_line.iloc[-1])
    last_hist = float(histogram.iloc[-1])

    # RF-04.2: alcista si linea MACD > linea de senal
    trend = "alcista" if last_macd > last_signal else "bajista"

    # Riesgo relativo a la magnitud del histograma frente a la desviacion tipica
    # de la propia serie (evita fijar un umbral en pesos, que dependeria del precio
    # del instrumento). |hist| pequeno = tendencia debil = riesgo bajo; grande = alto.
    hist_std = float(histogram.dropna().std()) or 1.0
    magnitude = abs(last_hist) / hist_std
    if magnitude >= 1.5:
        risk = "alto"
    elif magnitude >= 0.5:
        risk = "medio"
    else:
        risk = "bajo"

    return {
        "indicator": "macd",
        "value": round(last_hist, 4),
        "unit": "pts",
        "risk_level": risk,
        "trend": trend,
        "macd_line": round(last_macd, 4),
        "signal_line": round(last_signal, 4),
    }


def compute_bollinger_bands(records, window: int = 20, num_std: float = 2.0):
    """Bandas de Bollinger. Umbral oficial: %B > 1 sobrecomprado, %B < 0 sobrevendido.

    - Banda media   = SMA(20)
    - Banda superior = SMA(20) + 2 * StdDev(20)
    - Banda inferior = SMA(20) - 2 * StdDev(20)
    - %B = (precio - inferior) / (superior - inferior)
    """
    close = _to_series(records)
    if len(close) < window:
        raise ValueError("No hay suficientes datos para calcular Bandas de Bollinger")

    middle, upper, lower = _bollinger_series(close, window, num_std)

    last_close = float(close.iloc[-1])
    last_upper = float(upper.iloc[-1])
    last_lower = float(lower.iloc[-1])
    last_middle = float(middle.iloc[-1])

    band_width = last_upper - last_lower
    if band_width <= 0:
        percent_b = 0.5
    else:
        percent_b = (last_close - last_lower) / band_width

    # RF-04.2: umbrales oficiales del %B
    if percent_b > 1:
        signal = "sobrecomprado"
        risk = "alto"
    elif percent_b < 0:
        signal = "sobrevendido"
        risk = "alto"
    elif 0.8 <= percent_b <= 1 or 0 <= percent_b <= 0.2:
        signal = "cercano_al_extremo"
        risk = "medio"
    else:
        signal = "normal"
        risk = "bajo"

    return {
        "indicator": "bandas_bollinger",
        "value": round(percent_b, 2),
        "unit": "%B",
        "risk_level": risk,
        "signal": signal,
        "upper": round(last_upper, 2),
        "lower": round(last_lower, 2),
        "middle": round(last_middle, 2),
        "price": round(last_close, 2),
    }


def compute_ma_series(records, short_window: int = 50, long_window: int = 200):
    """Serie de precios y de todos los indicadores para graficar.

    Retorna listas alineadas por fecha; los primeros puntos de cada
    indicador quedan en `None` mientras no hay suficiente historial
    (calentamiento de la ventana). Ademas de MA corta/larga, incluye
    Bandas de Bollinger, RSI y MACD (linea, senal, histograma) para
    que el frontend pueda alternar la visibilidad de cada uno como
    overlay sobre el precio (Bollinger/MAs) o en subgraficos aparte
    (RSI/MACD, que tienen escala propia).
    """
    df = _to_frame(records)
    close = df["close"]

    short_window, long_window = _ma_windows(len(close), short_window, long_window)
    sma_short = close.rolling(window=short_window).mean()
    sma_long = close.rolling(window=long_window).mean()

    # Ventanas reducidas cuando la historia es muy corta para no dejar toda
    # la serie en None.
    bb_window = min(20, max(2, len(close) // 3))
    bb_middle, bb_upper, bb_lower = _bollinger_series(close, bb_window)

    rsi_window = min(14, max(2, len(close) // 3))
    rsi_series = _rsi_series(close, rsi_window)

    macd_line, signal_line, macd_hist = _macd_series(close)

    def _to_list(series, digits=2):
        return [None if pd.isna(v) else round(float(v), digits) for v in series]

    result = {
        "dates": [d.strftime("%Y-%m-%d") for d in df.index],
        "close": _to_list(close),
        "sma_short": _to_list(sma_short),
        "sma_long": _to_list(sma_long),
        "short_window": short_window,
        "long_window": long_window,
        "bollinger_upper": _to_list(bb_upper),
        "bollinger_middle": _to_list(bb_middle),
        "bollinger_lower": _to_list(bb_lower),
        "bollinger_window": bb_window,
        "rsi": _to_list(rsi_series),
        "rsi_window": rsi_window,
        "macd_line": _to_list(macd_line, digits=4),
        "macd_signal": _to_list(signal_line, digits=4),
        "macd_histogram": _to_list(macd_hist, digits=4),
    }

    for col in ("open", "high", "low"):
        if col in df.columns:
            result[col] = _to_list(df[col])

    return result


INDICATOR_FUNCTIONS = {
    "rsi": compute_rsi,
    "medias_moviles": compute_moving_averages,
    "macd": compute_macd,
    "bandas_bollinger": compute_bollinger_bands,
}


INDICATOR_TYPES = tuple(INDICATOR_FUNCTIONS)


def compute_indicator(indicator: str, records: list):
    if indicator not in INDICATOR_FUNCTIONS:
        raise ValueError(f"Indicador desconocido: {indicator}")
    return INDICATOR_FUNCTIONS[indicator](records)
