"""Validacion de coherencia semantica (RF-04.2, RF-13).

Contrasta el contenido de la explicacion generada con el valor real
del indicador, para mitigar alucinaciones del modelo y detectar
distorsiones. Reutiliza las mismas reglas de clasificacion de riesgo
del Extractor para evitar que el validador y el generador diverjan.
"""

from src.extractor.indicators import compute_indicator
from .explainer import RISK_LABELS


def validate_coherence(indicator_data: dict, explanation_text: str):
    """Retorna (es_coherente: bool, motivo: str | None).

    Regla 1: el nivel de riesgo mencionado en el texto debe coincidir
    con el nivel de riesgo calculado a partir del valor numerico real.
    Regla 2: el valor numerico del indicador debe aparecer citado en
    el texto (evita explicaciones genericas desconectadas del dato).
    """
    indicator = indicator_data["indicator"]
    risk_level = indicator_data["risk_level"]
    expected_label = RISK_LABELS.get(risk_level, "")

    if expected_label and expected_label not in explanation_text.lower():
        return False, f"El texto no menciona el nivel de riesgo esperado ({expected_label})."

    value_str = str(indicator_data["value"])
    if value_str not in explanation_text:
        return False, "El texto no cita el valor numerico real del indicador."

    return True, None


def revalidate_from_raw(records: list, indicator: str, risk_level_in_text: str):
    """Recalcula el indicador desde los datos crudos y compara el riesgo.

    Util cuando se quiere auditar una explicacion ya persistida sin
    confiar en el `risk_level` guardado junto a ella.
    """
    recomputed = compute_indicator(indicator, records)
    return recomputed["risk_level"] == risk_level_in_text, recomputed
