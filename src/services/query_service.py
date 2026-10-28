"""Flujo compartido de una consulta: indicador -> explicacion -> registro (RF-04 a RF-06, RNF-01.2).

Lo usan `/api/query`, `/api/regenerate` y `/api/perfil/regenerar`; antes cada ruta
repetia estos pasos con los mismos argumentos de configuracion.
"""

import math
import time
import uuid

from flask import current_app, session

from src.catalog import resolve_display_name
from src.extensions import db
from src.extractor import ExtractionError, get_indicator
from src.nlp import generate_explanation, regenerate_explanation, validate_coherence
from src.nlp.levels import DEFAULT_LEVEL
from src.profile.models import QueryLog


def get_session_id() -> str:
    """Identificador anonimo de la sesion de Flask; lo crea si todavia no existe."""
    if "sid" not in session:
        session["sid"] = str(uuid.uuid4())
    return session["sid"]


def has_value(indicator_data: dict) -> bool:
    """False si el indicador no trae valor o es NaN (precios huecos en la fuente)."""
    val = indicator_data.get("value")
    return not (val is None or (isinstance(val, float) and math.isnan(val)))


def fetch_indicator(symbol: str, indicator: str, days: int) -> dict:
    return get_indicator(
        symbol,
        indicator,
        days=days,
        alpha_vantage_key=current_app.config["ALPHAVANTAGE_API_KEY"],
        cache_ttl_seconds=current_app.config["CACHE_TTL_SECONDS"],
    )


def explain(indicator_data: dict, *, symbol: str, detail_level: str, variant: int = 0, previous_variant=None) -> dict:
    """Redacta la explicacion. Con `previous_variant` genera una redaccion alternativa (RF-06.2)."""
    options = dict(
        use_finbert=current_app.config["USE_FINBERT"],
        detail_level=detail_level,
        display_name=resolve_display_name(symbol),
        use_llm=current_app.config.get("USE_LLM", False),
        llm_api_key=current_app.config.get("GROQ_API_KEY", ""),
    )
    if previous_variant is None:
        return generate_explanation(indicator_data, variant=variant, **options)
    return regenerate_explanation(indicator_data, previous_variant, **options)


def run_query(symbol: str, indicator: str, days: int, *, detail_level: str = DEFAULT_LEVEL, variant: int = 0, previous_variant=None):
    """Obtiene el indicador y su explicacion. Devuelve (datos, explicacion, ms empleados)."""
    started = time.perf_counter()
    indicator_data = fetch_indicator(symbol, indicator, days)
    explanation = explain(
        indicator_data, symbol=symbol, detail_level=detail_level, variant=variant, previous_variant=previous_variant
    )
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return indicator_data, explanation, elapsed_ms


def log_and_validate(session_id, symbol, indicator, indicator_data, explanation, elapsed_ms, user_id=None, is_regeneration=False):
    """Guarda el `QueryLog` y valida la coherencia texto-dato. Devuelve (coherente, motivo).

    Guardarrail: si el valor es NaN, Flask devolvia un HTML 500 al frontend
    ("Unexpected token '<'"). Aqui se convierte en un `ExtractionError` amigable, que es
    la ultima defensa antes de tocar la base (tambien se ataca en `_to_series` y `_fetch_yahoo`).
    """
    if not has_value(indicator_data):
        raise ExtractionError("No hay datos suficientes para calcular este indicador en este momento.")

    db.session.add(
        QueryLog(
            session_id=session_id,
            instrument=symbol,
            indicator=indicator,
            source=indicator_data["source"],
            processing_time_ms=elapsed_ms,
            user_id=user_id,
            is_regeneration=is_regeneration,
            explanation_text=explanation["text"],
            variant=explanation["variant"],
            value=indicator_data["value"],
            unit=indicator_data.get("unit"),
            risk_level=indicator_data.get("risk_level"),
            period_days=indicator_data.get("period_days"),
        )
    )
    db.session.commit()
    return validate_coherence(indicator_data, explanation["text"])
