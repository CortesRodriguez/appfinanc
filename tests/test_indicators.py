import datetime as dt

from src.extractor.indicators import (
    compute_bollinger_bands,
    compute_macd,
    compute_moving_averages,
    compute_rsi,
)


def _records(prices, start="2026-01-01"):
    start_date = dt.date.fromisoformat(start)
    return [
        {"date": (start_date + dt.timedelta(days=i)).isoformat(), "close": price}
        for i, price in enumerate(prices)
    ]


# RSI ----------------------------------------------------------------------

def test_rsi_extreme_after_sustained_gains():
    prices = [100 + i for i in range(30)]  # solo sube: RSI deberia ser muy alto
    result = compute_rsi(_records(prices))
    assert result["indicator"] == "rsi"
    assert result["value"] > 70
    # RF-04.2: RSI > 70 → sobrecomprado
    assert result["signal"] == "sobrecomprado"
    assert result["risk_level"] == "alto"


def test_rsi_extreme_after_sustained_losses():
    prices = [200 - i for i in range(30)]
    result = compute_rsi(_records(prices))
    assert result["value"] < 30
    assert result["signal"] == "sobrevendido"
    assert result["risk_level"] == "alto"


# Medias móviles ----------------------------------------------------------

def test_moving_averages_detects_uptrend():
    prices = [100 + i * 2 for i in range(60)]
    result = compute_moving_averages(_records(prices))
    assert result["trend"] == "alcista"
    assert result["value"] > 0
    # RF-04.2: alcista implica MA corta > MA larga
    assert result["sma_short"] > result["sma_long"]


def test_moving_averages_detects_downtrend():
    prices = [200 - i * 2 for i in range(60)]
    result = compute_moving_averages(_records(prices))
    assert result["trend"] == "bajista"
    assert result["value"] < 0
    assert result["sma_short"] < result["sma_long"]


# MACD --------------------------------------------------------------------

def test_macd_bullish_on_sustained_uptrend():
    prices = [100 + i * 2 for i in range(60)]
    result = compute_macd(_records(prices))
    assert result["indicator"] == "macd"
    # RF-04.2: alcista si linea MACD > linea de senal
    assert result["macd_line"] > result["signal_line"]
    assert result["trend"] == "alcista"


def test_macd_bearish_on_sustained_downtrend():
    prices = [200 - i * 2 for i in range(60)]
    result = compute_macd(_records(prices))
    assert result["macd_line"] < result["signal_line"]
    assert result["trend"] == "bajista"


# Bandas de Bollinger ------------------------------------------------------

def test_bollinger_overbought_when_price_breaks_above_upper():
    # Precio plano y luego un salto brusco al alza: %B debe superar 1
    prices = [100.0] * 30 + [150.0]
    result = compute_bollinger_bands(_records(prices))
    assert result["indicator"] == "bandas_bollinger"
    # RF-04.2: %B > 1 → sobrecomprado
    assert result["value"] > 1
    assert result["signal"] == "sobrecomprado"
    assert result["risk_level"] == "alto"


def test_bollinger_oversold_when_price_breaks_below_lower():
    prices = [100.0] * 30 + [50.0]
    result = compute_bollinger_bands(_records(prices))
    assert result["value"] < 0
    assert result["signal"] == "sobrevendido"
    assert result["risk_level"] == "alto"


def test_bollinger_normal_when_price_inside_bands():
    prices = [100 + (i % 3) for i in range(30)]  # oscilacion pequena
    result = compute_bollinger_bands(_records(prices))
    assert 0 <= result["value"] <= 1
    assert result["signal"] in ("normal", "cercano_al_extremo")
