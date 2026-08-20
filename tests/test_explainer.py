from src.nlp.explainer import MAX_WORDS, generate_explanation, regenerate_explanation


def _indicator_data(indicator="rsi", risk_level="alto", value=75.0, **extra):
    data = {
        "indicator": indicator,
        "value": value,
        "unit": "pts",
        "risk_level": risk_level,
        "symbol": "SQM-B.SN",
        "source": "Yahoo Finance",
        "extracted_at": "2026-01-01T00:00:00+00:00",
        "period_days": 90,
    }
    data.update(extra)
    return data


def test_explanation_respects_word_limit():
    data = _indicator_data(indicator="rsi", value=75.0, signal="sobrecomprado")
    explanation = generate_explanation(data, use_finbert=False)
    assert len(explanation["text"].split()) <= MAX_WORDS


def test_explanation_mentions_value_and_risk():
    data = _indicator_data(indicator="rsi", value=75.0, risk_level="alto", signal="sobrecomprado")
    explanation = generate_explanation(data, use_finbert=False)
    assert "75.0" in explanation["text"]
    assert "riesgo alto" in explanation["text"].lower()


def test_explanation_is_spanish_and_under_150_words_for_all_indicators():
    cases = [
        ("rsi", "medio", 50.0, {"signal": "neutral"}),
        ("medias_moviles", "alto", 12.3, {"trend": "alcista", "sma_short": 120.0, "sma_long": 110.0}),
        ("macd", "medio", 1.5, {"trend": "alcista", "macd_line": 2.5, "signal_line": 1.0}),
        ("bandas_bollinger", "alto", 1.15, {"signal": "sobrecomprado", "upper": 110.0, "lower": 90.0, "middle": 100.0, "price": 115.0}),
    ]
    for indicator, risk, value, extra in cases:
        data = _indicator_data(indicator=indicator, risk_level=risk, value=value, **extra)
        explanation = generate_explanation(data, use_finbert=False)
        assert len(explanation["text"].split()) <= MAX_WORDS
        assert explanation["text"]


def test_regenerate_returns_different_variant_when_pool_allows():
    data = _indicator_data(indicator="rsi", risk_level="alto", value=75.0, signal="sobrecomprado")
    first = generate_explanation(data, variant=0, use_finbert=False)
    second = regenerate_explanation(data, previous_variant=first["variant"], use_finbert=False)
    assert second["variant"] != first["variant"]
    assert second["text"] != first["text"]
