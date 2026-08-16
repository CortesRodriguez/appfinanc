import datetime as dt

from src.extractor.indicators import (
    compute_moving_averages,
    compute_return,
    compute_rsi,
    compute_volatility,
)


def _records(prices, start="2026-01-01"):
    start_date = dt.date.fromisoformat(start)
    return [
        {"date": (start_date + dt.timedelta(days=i)).isoformat(), "close": price}
        for i, price in enumerate(prices)
    ]


def test_volatility_low_for_stable_prices():
    prices = [100 + (0.05 if i % 2 == 0 else -0.05) for i in range(60)]
    result = compute_volatility(_records(prices))
    assert result["indicator"] == "volatilidad"
    assert result["risk_level"] == "bajo"


def test_volatility_high_for_erratic_prices():
    prices = []
    price = 100
    for i in range(60):
        price *= 1.08 if i % 2 == 0 else 0.90
        prices.append(price)
    result = compute_volatility(_records(prices))
    assert result["risk_level"] == "alto"


def test_rsi_extreme_after_sustained_gains():
    prices = [100 + i for i in range(30)]  # solo sube: RSI deberia ser muy alto
    result = compute_rsi(_records(prices))
    assert result["indicator"] == "rsi"
    assert result["value"] > 70
    assert result["risk_level"] == "alto"


def test_moving_averages_detects_uptrend():
    prices = [100 + i * 2 for i in range(60)]
    result = compute_moving_averages(_records(prices))
    assert result["trend"] == "alcista"
    assert result["value"] > 0


def test_moving_averages_detects_downtrend():
    prices = [200 - i * 2 for i in range(60)]
    result = compute_moving_averages(_records(prices))
    assert result["trend"] == "bajista"
    assert result["value"] < 0


def test_return_positive_and_negative():
    up = compute_return(_records([100, 105, 110, 120]))
    assert up["value"] > 0

    down = compute_return(_records([100, 95, 90, 80]))
    assert down["value"] < 0
    assert down["risk_level"] in ("medio", "alto")
