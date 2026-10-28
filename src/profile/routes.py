"""Rutas del perfil de aprendizaje (RF-13, RF-14, CU-26 a CU-32)."""

import time
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, url_for
from flask_jwt_extended import get_jwt_identity, jwt_required, verify_jwt_in_request

from src.auth.models import User
from src.auth.service import AuthError, normalize_experience
from src.constants import INDICATOR_SHORT_LABELS
from src.profile.models import QueryLog
from src.extensions import db
from src.extractor import ExtractionError, get_indicator
from src.nlp import regenerate_explanation
from src.web.routes import _get_session_id, _log_and_validate, _resolve_display_name

from src.nlp.levels import LEVEL_LABELS
from .service import build_learning_profile, get_detail_level, recent_queries, recent_visits

bp = Blueprint("profile", __name__)


def _profile_with_names(user_id):
    """Perfil con nombres de empresa legibles (ej. "Banco Santander" en vez de BSANTANDER.SN)."""
    profile = build_learning_profile(user_id)
    for row in profile["top_instruments"]:
        row["name"] = _resolve_display_name(row["instrument"])
    if profile["top_indicator_instrument"]:
        profile["top_indicator_instrument_name"] = _resolve_display_name(profile["top_indicator_instrument"])
    return profile


@bp.route("/perfil")
def profile_page():
    try:
        verify_jwt_in_request()
    except Exception:  # noqa: BLE001 - sin sesion valida: se pide iniciar sesion (CU-26, precondicion CU-25)
        return redirect(url_for("auth.login_page", next="perfil"))

    user_id = int(get_jwt_identity())
    user = db.session.get(User, user_id)
    profile = _profile_with_names(user_id)

    history = recent_queries(user_id, limit=current_app.config["HISTORY_MAX_ITEMS"])
    for q in history:
        q.display_name = _resolve_display_name(q.instrument)
    visits = recent_visits(user_id)
    for v in visits:
        v["name"] = _resolve_display_name(v["instrument"])

    return render_template(
        "profile.html",
        user=user,
        profile=profile,
        indicator_labels=INDICATOR_SHORT_LABELS,
        level_labels=LEVEL_LABELS,
        history=history,
        visits=visits,
    )


@bp.route("/api/perfil")
@jwt_required()
def api_profile():
    user_id = int(get_jwt_identity())
    profile = _profile_with_names(user_id)
    profile["indicator_label"] = INDICATOR_SHORT_LABELS.get(profile["top_indicator"], profile["top_indicator"])
    return jsonify(profile)


@bp.route("/api/perfil/experiencia", methods=["PATCH"])
@jwt_required()
def api_profile_experience():
    """Guarda o corrige la experiencia declarada (RF-13.2). Vacio = quitarla."""
    payload = request.get_json(silent=True) or {}
    try:
        experience = normalize_experience(payload.get("experience_level"))
    except AuthError as exc:
        return jsonify({"error": str(exc)}), exc.status

    user = db.session.get(User, int(get_jwt_identity()))
    if experience != user.experience_level:
        # Declarar otra experiencia reinicia el punto de partida de todos los indicadores:
        # las regeneraciones anteriores dejan de bajar el nivel.
        user.level_reset_at = datetime.now(timezone.utc)
    user.experience_level = experience
    db.session.commit()

    profile = build_learning_profile(user.id)
    return jsonify(
        {
            "experience_level": experience,
            "detail_levels": profile["detail_levels"],
            "detail_sources": profile["detail_sources"],
        }
    )


@bp.route("/api/perfil/regenerar", methods=["POST"])
@jwt_required()
def api_profile_regenerate():
    """RF-14.5 / CU-32: el perfil reutiliza la ultima explicacion guardada; este
    endpoint genera una redaccion nueva solo cuando el usuario la pide."""
    user_id = int(get_jwt_identity())
    profile = build_learning_profile(user_id)

    indicator = profile["top_indicator"]
    if not indicator:
        return jsonify({"error": "Aún no hay suficientes datos para regenerar tu resumen de perfil."}), 404

    last_log = (
        QueryLog.query.filter_by(user_id=user_id, indicator=indicator)
        .order_by(QueryLog.created_at.desc(), QueryLog.id.desc())
        .first()
    )
    instrument = last_log.instrument
    # RF-13.2: mismo nivel de detalle que recibiria en el dashboard.
    detail_level = get_detail_level(user_id, indicator)

    try:
        started = time.perf_counter()
        indicator_data = get_indicator(
            instrument,
            indicator,
            days=180,
            alpha_vantage_key=current_app.config["ALPHAVANTAGE_API_KEY"],
            cache_ttl_seconds=current_app.config["CACHE_TTL_SECONDS"],
        )
        explanation = regenerate_explanation(
            indicator_data,
            last_log.variant or 0,
            use_finbert=current_app.config["USE_FINBERT"],
            detail_level=detail_level,
            display_name=_resolve_display_name(instrument),
            use_llm=current_app.config.get("USE_LLM", False),
            llm_api_key=current_app.config.get("GROQ_API_KEY", ""),
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        coherent, _ = _log_and_validate(
            _get_session_id(), instrument, indicator, indicator_data, explanation, elapsed_ms,
            user_id=user_id, is_regeneration=True,
        )
    except ExtractionError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 502

    return jsonify(
        {
            "indicator": indicator,
            "instrument": instrument,
            "explanation": explanation["text"],
            "detail_level": detail_level,
            "coherent": coherent,
            "total_queries": profile["total_queries"] + 1,
            "regenerations": profile["top_indicator_regenerations"] + 1,
        }
    )
