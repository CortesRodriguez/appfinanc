from src.nlp.explainer import MAX_WORDS, generate_explanation, regenerate_explanation


def _indicator_data(indicator="volatilidad", risk_level="alto", value=35.2, **extra):
    data = {
        "indicator": indicator,
        "value": value,
        "unit": "%",
        "risk_level": risk_level,
        "symbol": "SQM-B.SN",
        "source": "Yahoo Finance",
        "extracted_at": "2026-01-01T00:00:00+00:00",
        "period_days": 90,
    }
    data.update(extra)
    return data


def test_explanation_respects_word_limit():
    data = _indicator_data()
    explanation = generate_explanation(data)
    assert len(explanation["text"].split()) <= MAX_WORDS


def test_explanation_mentions_value_and_risk():
    data = _indicator_data(value=35.2, risk_level="alto")
    explanation = generate_explanation(data)
    assert "35.2" in explanation["text"]
    assert "riesgo alto" in explanation["text"].lower()


def test_explanation_is_spanish_and_under_150_words_for_all_indicators():
    for indicator, risk in [
        ("volatilidad", "bajo"),
        ("rsi", "medio"),
        ("medias_moviles", "alto"),
        ("rentabilidad", "medio"),
    ]:
        data = _indicator_data(indicator=indicator, risk_level=risk, value=12.3, trend="alcista")
        explanation = generate_explanation(data)
        assert len(explanation["text"].split()) <= MAX_WORDS
        assert explanation["text"]


def test_regenerate_returns_different_variant_when_pool_allows():
    data = _indicator_data(indicator="volatilidad", risk_level="alto", value=35.2)
    first = generate_explanation(data, variant=0)
    second = regenerate_explanation(data, previous_variant=first["variant"])
    assert second["variant"] != first["variant"]
    assert second["text"] != first["text"]
