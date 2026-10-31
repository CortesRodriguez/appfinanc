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


def test_validate_flags_ma_trend_opposite_to_the_calculated_one():
    data = {
        "indicator": "medias_moviles",
        "value": -5.0,
        "unit": "%",
        "risk_level": "bajo",
        "trend": "bajista",
        "sma_short": 95.0,
        "sma_long": 100.0,
        "symbol": "SQM-B.SN",
        "source": "Yahoo Finance",
        "extracted_at": "2026-01-01T00:00:00+00:00",
        "period_days": 90,
    }
    # El dato dice bajista (media corta bajo la larga) y el texto afirma lo contrario
    text = "SQM-B.SN muestra una tendencia alcista de -5.0% (riesgo bajo)."
    coherent, reason = validate_coherence(data, text)
    assert coherent is False
    assert "bajista" in (reason or "")


# Lagunas cerradas y garantia de no rechazar texto correcto --------------------

import pytest


def _ma_data(trend="alcista", value=5.0, risk_level="bajo", short=10.0, long=9.0):
    return {"indicator": "medias_moviles", "value": value, "risk_level": risk_level, "trend": trend,
            "sma_short": short, "sma_long": long, "symbol": "SQM-B.SN"}


CONTRADICCIONES = [
    (_rsi_data("medio", 50.0, "neutral"), "El RSI marca 50.0 (riesgo medio): hay sobrecompra clara."),
    (_rsi_data("medio", 50.0, "neutral"), "El RSI marca 50.0 (riesgo medio): estamos en sobreventa."),
    (_rsi_data("medio", 50.0, "neutral"), "RSI 50.0 (riesgo medio), en sobreventa (bajo 30)."),
    (_bb_data(0.5, "normal", "bajo"), "El %B es 0.5 (riesgo bajo): el precio está en sobrecompra."),
    (_bb_data(0.5, "normal", "bajo"), "El %B es 0.5 (riesgo bajo): el precio está en sobreventa."),
    (_macd_data("alcista", 0.3, "bajo"), "El MACD marca 0.3 (riesgo bajo): tendencia bajista."),
    (_ma_data("alcista"), "Las medias móviles marcan 5.0% (riesgo bajo): tendencia bajista."),
    (_ma_data("bajista", -5.0, short=9.0, long=10.0), "Las medias marcan -5.0% (riesgo bajo): tendencia alcista."),
]


@pytest.mark.parametrize("data,text", CONTRADICCIONES)
def test_rechaza_una_afirmacion_que_contradice_el_dato(data, text):
    assert validate_coherence(data, text)[0] is False


def test_el_valor_no_se_confunde_con_parte_de_otro_numero():
    # "15.0" contiene "5.0", pero no es el valor del indicador
    data = _rsi_data("alto", 5.0, "sobrevendido")
    assert validate_coherence(data, "El RSI marca 15.0 (riesgo alto), en sobreventa.")[0] is False
    assert validate_coherence(data, "El RSI marca 5.0 (riesgo alto), en sobreventa.")[0] is True


CORRECTOS = [
    # negacion y definicion de umbrales no son afirmaciones
    (_rsi_data("medio", 50.0, "neutral"), "El RSI marca 50.0 (riesgo medio): no hay sobrecompra ni sobreventa."),
    (_rsi_data("medio", 50.0, "neutral"), "RSI 50.0, riesgo medio. No está en sobrecompra; la zona neutral va de 30 a 70."),
    (_rsi_data("medio", 50.0, "neutral"), "RSI de 50.0 (riesgo medio): sobre 70 se considera sobrecompra y bajo 30, sobreventa."),
    (_rsi_data("medio", 50.0, "neutral"), "El RSI vale 50.0 (riesgo medio). Si superara 70 hablaríamos de sobrecompra."),
    (_rsi_data("medio", 50.0, "neutral"), "El RSI marca 50.0 (riesgo medio): ni sobrecomprado ni sobrevendido."),
    (_bb_data(0.5, "normal", "bajo"), "%B 0.5 (riesgo bajo). Para hablar de sobrecompra tendría que superar 1."),
    (_macd_data("bajista", -0.59, "alto"), "El MACD marca -0.59 (riesgo alto): tendencia bajista, no alcista."),
    (_ma_data("alcista"), "Medias móviles 5.0% (riesgo bajo): alcista; no hay cruce bajista."),
    # afirmaciones que si coinciden con el dato, en cualquiera de las dos formas
    (_rsi_data("alto", 78.5, "sobrecomprado"), "El RSI de BCI está en 78.5 (riesgo alto): sobrecompra, por encima de 70."),
    (_rsi_data("alto", 78.5, "sobrecomprado"), "RSI 78.5, riesgo alto: sobrecomprado."),
    (_rsi_data("alto", 15.2, "sobrevendido"), "El RSI marca 15.2 (riesgo alto): sobreventa, bajo 30."),
    (_bb_data(1.1, "sobrecomprado", "alto"), "El %B llegó a 1.1 (riesgo alto): sobrecompra, sobre la banda superior."),
    # formato del numero
    (_rsi_data("medio", 46.6, "neutral"), "El RSI es 46,6 (riesgo medio), zona neutral."),
    (_rsi_data("medio", 46.5, "neutral"), "El RSI es 46.50 (riesgo medio), zona neutral."),
    (_rsi_data("medio", 50.0, "neutral"), "El RSI marca 50 (riesgo medio)."),
    (_rsi_data("medio", 46.59, "neutral"), "El RSI de BCI es 46.59. Es riesgo medio."),
    (_bb_data(-0.2, "sobrevendido", "alto"), "El %B es −0.2 (riesgo alto): sobreventa, bajo la banda inferior."),
    # las medias redondeadas pueden quedar iguales: el texto no debe rechazarse por eso
    (_ma_data("bajista", 0.0, "medio", short=9.99, long=9.99), "Medias móviles 0.0% (riesgo medio): tendencia bajista débil."),
]


@pytest.mark.parametrize("data,text", CORRECTOS)
def test_no_rechaza_texto_correcto(data, text):
    assert validate_coherence(data, text) == (True, None)


def test_todas_las_plantillas_son_coherentes():
    from src.nlp.levels import LEVELS
    from src.nlp.templates import TEMPLATES

    ejemplos = {
        "rsi": {"alto": ("sobrecomprado", 78.5), "medio": ("neutral", 62.0), "bajo": ("neutral", 50.0)},
        "bandas_bollinger": {"alto": ("sobrecomprado", 1.1), "medio": ("cercano_al_extremo", 0.8), "bajo": ("normal", 0.5)},
    }
    for nivel in LEVELS:
        for indicador, por_riesgo in TEMPLATES[nivel].items():
            for riesgo, variantes in por_riesgo.items():
                if indicador in ejemplos:
                    signal, value = ejemplos[indicador][riesgo]
                    data = {"indicator": indicador, "value": value, "risk_level": riesgo, "signal": signal, "symbol": "BCI.SN"}
                else:
                    trend = "alcista"
                    data = {"indicator": indicador, "value": 1.2, "risk_level": riesgo, "trend": trend,
                            "sma_short": 105.0, "sma_long": 100.0, "symbol": "BCI.SN"}
                for v in range(len(variantes)):
                    text = generate_explanation(data, variant=v, use_finbert=False, detail_level=nivel)["text"]
                    assert validate_coherence(data, text)[0], (nivel, indicador, riesgo, v, text)
