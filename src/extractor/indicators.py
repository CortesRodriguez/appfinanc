"""Calculo de indicadores financieros y clasificacion de riesgo.

Implementa RF-02.1 (volatilidad, RSI, medias moviles, rentabilidad) y
RF-06.1 (clasificacion del nivel de riesgo relativo en bajo/medio/alto).
Los umbrales usados son reglas de validacion financiera simples,
documentadas aqui, que tambien sirven de base para el validador de
coherencia semantica (RF-04.2 / RF-13).
"""

import numpy as np
import pandas as pd

INDICATOR_TYPES = ("volatilidad", "rsi", "medias_moviles", "rentabilidad")


def _to_series(records):
    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    return df.set_index("date")["close"]


def compute_volatility(records):
    close = _to_series(records)
    returns = close.pct_change().dropna()
    if returns.empty:
        raise ValueError("No hay suficientes datos para calcular volatilidad")
    annualized_pct = float(returns.std() * np.sqrt(252) * 100)

    if annualized_pct < 15:
        risk = "bajo"
    elif annualized_pct < 30:
        risk = "medio"
    else:
        risk = "alto"

    return {"indicator": "volatilidad", "value": round(annualized_pct, 2), "unit": "%", "risk_level": risk}


def compute_rsi(records, window: int = 14):
    close = _to_series(records)
    if len(close) < window + 1:
        raise ValueError("No hay suficientes datos para calcular RSI")

    delta = close.diff().dropna()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)

    avg_gain = gains.rolling(window=window).mean()
    avg_loss = losses.rolling(window=window).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    # Sin perdidas en la ventana (solo subidas): RSI = 100 por definicion
    rsi = rsi.where(~((avg_loss == 0) & (avg_gain > 0)), 100.0)
    rsi_valid = rsi.dropna()
    last_rsi = float(rsi_valid.iloc[-1]) if not rsi_valid.empty else 50.0

    if last_rsi >= 70:
        risk = "alto"
    elif last_rsi <= 30:
        risk = "alto"
    else:
        risk = "medio" if 40 <= last_rsi <= 60 else "bajo"

    return {"indicator": "rsi", "value": round(last_rsi, 2), "unit": "pts", "risk_level": risk}


def compute_moving_averages(records, short_window: int = 50, long_window: int = 200):
    close = _to_series(records)
    if len(close) < 5:
        raise ValueError("No hay suficientes datos para calcular medias moviles")

    short_window = min(short_window, max(2, len(close) // 2))
    long_window = min(long_window, len(close))

    sma_short = close.rolling(window=short_window).mean().iloc[-1]
    sma_long = close.rolling(window=long_window).mean().iloc[-1]

    diff_pct = float((sma_short - sma_long) / sma_long * 100)
    trend = "alcista" if diff_pct > 0 else "bajista"
    risk = "medio" if abs(diff_pct) < 5 else ("alto" if abs(diff_pct) >= 10 else "medio")

    return {
        "indicator": "medias_moviles",
        "value": round(diff_pct, 2),
        "unit": "%",
        "risk_level": risk,
        "trend": trend,
        "sma_short": round(float(sma_short), 2),
        "sma_long": round(float(sma_long), 2),
    }


def compute_return(records):
    close = _to_series(records)
    if len(close) < 2:
        raise ValueError("No hay suficientes datos para calcular rentabilidad")

    first, last = float(close.iloc[0]), float(close.iloc[-1])
    pct = (last - first) / first * 100

    if pct > 0:
        risk = "bajo" if pct < 10 else "medio"
    else:
        risk = "medio" if pct > -10 else "alto"

    return {"indicator": "rentabilidad", "value": round(pct, 2), "unit": "%", "risk_level": risk}


def compute_ma_series(records, short_window: int = 50, long_window: int = 200):
    """Serie de precios y medias moviles para graficar (tendencia, vista de escenarios).

    Retorna listas alineadas por fecha; los primeros puntos de cada media
    quedan en `None` mientras no hay suficiente historial para calcularla
    (periodo de calentamiento de la media movil).
    """
    df = pd.DataFrame(records)
    if df.empty:
        raise ValueError("No hay suficientes datos para construir el grafico")

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").set_index("date")
    close = df["close"]

    short_window = min(short_window, max(2, len(close) // 2))
    long_window = min(long_window, len(close))

    sma_short = close.rolling(window=short_window).mean()
    sma_long = close.rolling(window=long_window).mean()

    def _to_list(series):
        return [None if pd.isna(v) else round(float(v), 2) for v in series]

    result = {
        "dates": [d.strftime("%Y-%m-%d") for d in df.index],
        "close": _to_list(close),
        "sma_short": _to_list(sma_short),
        "sma_long": _to_list(sma_long),
        "short_window": short_window,
        "long_window": long_window,
    }

    # OHLC: presente si la fuente lo entrega (Yahoo/Alpha Vantage actualizadas);
    # cache antiguo sin OHLC sigue sirviendo el gráfico de líneas.
    for col in ("open", "high", "low"):
        if col in df.columns:
            result[col] = _to_list(df[col])

    return result


INDICATOR_FUNCTIONS = {
    "volatilidad": compute_volatility,
    "rsi": compute_rsi,
    "medias_moviles": compute_moving_averages,
    "rentabilidad": compute_return,
}


def compute_indicator(indicator: str, records: list):
    if indicator not in INDICATOR_FUNCTIONS:
        raise ValueError(f"Indicador desconocido: {indicator}")
    return INDICATOR_FUNCTIONS[indicator](records)
