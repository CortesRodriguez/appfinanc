from src.nlp.explainer import generate_explanation
from src.nlp.validator import validate_coherence


def _rsi_data(risk_level="alto", value=75.0, signal="sobrecomprado"):
    return {
        "indicator": "rsi",
        "value": value,
        "unit": "pts",
        "risk_level": risk_level,
        "signal": signal,
        "symbol": "SQM-B.SN",
        "source": "Yahoo Finance",
        "extracted_at": "2026-01-01T00:00:00+00:00",
        "period_days": 90,
    }


def _macd_data(trend="alcista", value=1.23, risk_level="medio"):
    return {
        "indicator": "macd",
        "value": value,
        "unit": "pts",
        "risk_level": risk_level,
        "trend": trend,
        "macd_line": 2.5,
        "signal_line": 1.3,
        "symbol": "SQM-B.SN",
        "source": "Yahoo Finance",
        "extracted_at": "2026-01-01T00:00:00+00:00",
        "period_days": 90,
    }


def _bb_data(value=0.5, signal="normal", risk_level="bajo"):
    return {
        "indicator": "bandas_bollinger",
        "value": value,
        "unit": "%B",
        "risk_level": risk_level,
        "signal": signal,
        "upper": 110.0,
        "lower": 90.0,
        "middle": 100.0,
        "price": 100.0,
        "symbol": "SQM-B.SN",
        "source": "Yahoo Finance",
        "extracted_at": "2026-01-01T00:00:00+00:00",
        "period_days": 90,
    }


# Coherencia general ------------------------------------------------------

def test_validate_coherence_passes_for_generated_text_rsi():
    data = _rsi_data()
    explanation = generate_explanation(data, use_finbert=False)
    coherent, reason = validate_coherence(data, explanation["text"])
    assert coherent is True
    assert reason is None


def test_validate_coherence_flags_mismatched_risk_label():
    data = _rsi_data(risk_level="alto", value=75.0)
    misleading_text = "SQM-B.SN tiene riesgo bajo y está totalmente estable, con valor 75.0 puntos."
    coherent, reason = validate_coherence(data, misleading_text)
    assert coherent is False
    assert reason is not None


def test_validate_coherence_flags_missing_value():
    data = _rsi_data(value=75.0)
    text_without_value = "Este instrumento tiene riesgo alto en este momento."
    coherent, reason = validate_coherence(data, text_without_value)
    assert coherent is False


# Reglas específicas RF-04.2 ---------------------------------------------

def test_validate_flags_rsi_overbought_claim_when_value_not_high():
    # Valor 50 (neutral) pero texto afirma sobrecompra → incoherencia
    data = _rsi_data(risk_level="bajo", value=50.0, signal="neutral")
    text = "El RSI de SQM-B.SN es 50.0 puntos y está sobrecomprado (riesgo bajo)."
    coherent, reason = validate_coherence(data, text)
    assert coherent is False
    assert "sobrecompra" in (reason or "").lower() or "70" in (reason or "")


def test_validate_flags_macd_bullish_when_data_says_bearish():
    data = _macd_data(trend="bajista", value=-2.5)
    # Texto afirma "alcista" a pesar de que el dato es bajista
    text = "El MACD de SQM-B.SN muestra una señal alcista fuerte (histograma -2.5 puntos, riesgo medio)."
    coherent, reason = validate_coherence(data, text)
    assert coherent is False


def test_validate_flags_bollinger_overbought_when_percent_b_low():
    data = _bb_data(value=0.5, signal="normal", risk_level="bajo")
    text = "El %B de SQM-B.SN es 0.5 y el precio está sobrecomprado (riesgo bajo)."
    coherent, reason = validate_coherence(data, text)
    assert coherent is False


def test_validate_flags_ma_alcista_when_short_below_long():
    data = {
        "indicator": "medias_moviles",
        "value": -5.0,
        "unit": "%",
        "risk_level": "bajo",
        "trend": "alcista",
        "sma_short": 95.0,
        "sma_long": 100.0,
        "symbol": "SQM-B.SN",
        "source": "Yahoo Finance",
        "extracted_at": "2026-01-01T00:00:00+00:00",
        "period_days": 90,
    }
    # Datos contradictorios: trend=alcista pero sma_short < sma_long
    text = "SQM-B.SN muestra una tendencia alcista de -5.0% (riesgo bajo)."
    coherent, reason = validate_coherence(data, text)
    assert coherent is False
