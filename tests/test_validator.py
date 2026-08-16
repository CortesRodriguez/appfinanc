from src.nlp.explainer import generate_explanation
from src.nlp.validator import validate_coherence


def _indicator_data(indicator="volatilidad", risk_level="alto", value=35.2):
    return {
        "indicator": indicator,
        "value": value,
        "unit": "%",
        "risk_level": risk_level,
        "symbol": "SQM-B.SN",
        "source": "Yahoo Finance",
        "extracted_at": "2026-01-01T00:00:00+00:00",
        "period_days": 90,
    }


def test_validate_coherence_passes_for_generated_text():
    data = _indicator_data()
    explanation = generate_explanation(data)
    coherent, reason = validate_coherence(data, explanation["text"])
    assert coherent is True
    assert reason is None


def test_validate_coherence_flags_mismatched_risk_label():
    data = _indicator_data(risk_level="alto")
    # Texto generado para un escenario distinto (riesgo bajo), simulando una distorsion del modelo
    misleading_text = "SQM-B.SN tiene riesgo bajo y todo esta perfectamente estable, con valor 35.2%."
    coherent, reason = validate_coherence(data, misleading_text)
    assert coherent is False
    assert reason is not None


def test_validate_coherence_flags_missing_value():
    data = _indicator_data(value=35.2)
    text_without_value = "Este instrumento tiene riesgo alto en este momento."
    coherent, reason = validate_coherence(data, text_without_value)
    assert coherent is False
