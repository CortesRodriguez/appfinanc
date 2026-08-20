"""Validacion de coherencia semantica (RF-04.2, RF-13).

Contrasta el contenido de la explicacion generada contra el valor real
del indicador y contra los umbrales cualitativos oficiales, para mitigar
alucinaciones del modelo. Reglas verificadas:

  RSI:               sobrecomprado si > 70, sobrevendido si < 30
  Bandas de Bollinger: sobrecomprado si %B > 1, sobrevendido si %B < 0
  MACD:              alcista si linea MACD > linea de senal
  Medias moviles:    alcista si MA corta > MA larga

El validador consume el dict `indicator_data` ya calculado por el
Extractor (llegan por parametro `signal`, `trend`, `value`, etc.). No
importa nada del Extractor: la coherencia se comprueba solo con lo que
recibe, respetando la separacion entre componentes de dominio.
"""

from .explainer import RISK_LABELS


def _text_lower(text: str) -> str:
    return text.lower()


def _check_rsi_terms(indicator_data: dict, text_lower: str):
    signal = indicator_data.get("signal", "neutral")
    if signal == "sobrecomprado" and "sobrecomprado" not in text_lower and "sobrecompra" not in text_lower:
        # Explicacion silencia la senal cualitativa; permitido si el valor > 70 esta citado
        return True, None
    # Contradicciones estrictas: texto dice sobrecomprado con valor no > 70, etc.
    if "sobrecomprado" in text_lower and indicator_data["value"] <= 70:
        return False, "El texto afirma sobrecompra pero el RSI no supera 70."
    if "sobrevendido" in text_lower and indicator_data["value"] >= 30:
        return False, "El texto afirma sobreventa pero el RSI no cae bajo 30."
    return True, None


def _check_macd_terms(indicator_data: dict, text_lower: str):
    # Reglas RF-04.2: alcista si MACD > senal, bajista contrario. El campo
    # `trend` del indicador ya encapsula esta comparacion; el texto no debe
    # contradecirlo.
    trend = indicator_data.get("trend", "")
    if trend == "alcista" and "bajista" in text_lower and "alcista" not in text_lower:
        return False, "El texto describe una senal bajista pero el MACD calculado es alcista."
    if trend == "bajista" and "alcista" in text_lower and "bajista" not in text_lower:
        return False, "El texto describe una senal alcista pero el MACD calculado es bajista."
    return True, None


def _check_bollinger_terms(indicator_data: dict, text_lower: str):
    percent_b = indicator_data["value"]
    if "sobrecomprado" in text_lower and percent_b <= 1:
        return False, "El texto afirma sobrecompra pero %B no supera 1."
    if "sobrevendido" in text_lower and percent_b >= 0:
        return False, "El texto afirma sobreventa pero %B no es negativo."
    return True, None


def _check_ma_terms(indicator_data: dict, text_lower: str):
    trend = indicator_data.get("trend", "")
    sma_short = indicator_data.get("sma_short")
    sma_long = indicator_data.get("sma_long")
    if sma_short is None or sma_long is None:
        return True, None
    if trend == "alcista" and sma_short <= sma_long:
        return False, "Trend alcista incongruente: MA corta no supera a MA larga."
    if trend == "bajista" and sma_short >= sma_long:
        return False, "Trend bajista incongruente: MA corta no es inferior a MA larga."
    return True, None


_INDICATOR_CHECKS = {
    "rsi": _check_rsi_terms,
    "macd": _check_macd_terms,
    "bandas_bollinger": _check_bollinger_terms,
    "medias_moviles": _check_ma_terms,
}


def validate_coherence(indicator_data: dict, explanation_text: str):
    """Retorna (es_coherente: bool, motivo: str | None).

    Regla base: el nivel de riesgo mencionado en el texto debe coincidir
    con el nivel calculado; el valor numerico real debe aparecer citado.

    Regla especifica por indicador: se verifica que las categorias
    cualitativas mencionadas (sobrecomprado, alcista, etc.) sean
    consistentes con el valor numerico segun los umbrales de RF-04.2.
    """
    risk_level = indicator_data["risk_level"]
    expected_label = RISK_LABELS.get(risk_level, "")
    text_lower = _text_lower(explanation_text)

    if expected_label and expected_label not in text_lower:
        return False, f"El texto no menciona el nivel de riesgo esperado ({expected_label})."

    value_str = str(indicator_data["value"])
    if value_str not in explanation_text:
        return False, "El texto no cita el valor numerico real del indicador."

    check = _INDICATOR_CHECKS.get(indicator_data["indicator"])
    if check is not None:
        ok, reason = check(indicator_data, text_lower)
        if not ok:
            return False, reason

    return True, None
