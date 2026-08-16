"""Rutas del perfil de aprendizaje (RF-19, CU-13)."""

import uuid

from flask import Blueprint, current_app, jsonify, redirect, render_template, session, url_for
from flask_jwt_extended import get_jwt_identity, jwt_required, verify_jwt_in_request

from src.auth.models import User
from src.constants import INDICATOR_LABELS
from src.evaluation import ensure_evaluation_session
from src.evaluation.models import QueryLog
from src.extensions import db
from src.extractor import ExtractionError, get_indicator
from src.nlp import generate_explanation

from .service import build_learning_profile

bp = Blueprint("profile", __name__)


@bp.route("/perfil")
def profile_page():
    try:
        verify_jwt_in_request()
    except Exception:  # noqa: BLE001 - sin sesion valida: se pide iniciar sesion (CU-13, precondicion CU-12)
        return redirect(url_for("auth.login_page", next="perfil"))

    user_id = int(get_jwt_identity())
    user = db.session.get(User, user_id)
    profile = build_learning_profile(user_id)

    return render_template(
        "profile.html",
        user=user,
        profile=profile,
        indicator_labels=INDICATOR_LABELS,
    )


@bp.route("/api/perfil")
@jwt_required()
def api_profile():
    user_id = int(get_jwt_identity())
    profile = build_learning_profile(user_id)
    profile["indicator_label"] = INDICATOR_LABELS.get(profile["top_indicator"], profile["top_indicator"])
    return jsonify(profile)


def _ensure_session_id():
    """QueryLog.session_id es NOT NULL por diseno (RF-14, sesion anonima); una
    regeneracion disparada desde el perfil reutiliza la sesion de Flask del
    propio usuario, creandola si aun no existe."""
    if "sid" not in session:
        session["sid"] = str(uuid.uuid4())

    session_id = session["sid"]
    ensure_evaluation_session(session_id)
    return session_id


@bp.route("/api/perfil/regenerar", methods=["POST"])
@jwt_required()
def api_profile_regenerate():
    """RF-19.5: el usuario puede pedir explicitamente una explicacion nueva
    para el indicador de su perfil, en vez de reutilizar la ultima generada."""
    user_id = int(get_jwt_identity())
    profile = build_learning_profile(user_id)

    indicator = profile["top_indicator"]
    if not indicator:
        return jsonify({"error": "Aún no hay suficientes datos para regenerar tu resumen de perfil."}), 404

    last_log = (
        QueryLog.query.filter_by(user_id=user_id, indicator=indicator)
        .order_by(QueryLog.created_at.desc())
        .first()
    )
    if not last_log:
        return jsonify({"error": "No hay una consulta previa de este indicador para regenerar."}), 404

    try:
        indicator_data = get_indicator(
            last_log.instrument,
            indicator,
            days=180,
            alpha_vantage_key=current_app.config["ALPHAVANTAGE_API_KEY"],
            cache_ttl_seconds=current_app.config["CACHE_TTL_SECONDS"],
        )
    except ExtractionError as exc:
        return jsonify({"error": str(exc)}), 502

    next_variant = (last_log.variant or 0) + 1
    explanation = generate_explanation(indicator_data, variant=next_variant, detail_level="detallado")

    db.session.add(
        QueryLog(
            session_id=_ensure_session_id(),
            instrument=last_log.instrument,
            indicator=indicator,
            source=indicator_data["source"],
            processing_time_ms=0,
            user_id=user_id,
            is_regeneration=True,
            explanation_text=explanation["text"],
            variant=explanation["variant"],
        )
    )
    db.session.commit()

    return jsonify(
        {
            "indicator": indicator,
            "instrument": last_log.instrument,
            "explanation": explanation["text"],
        }
    )
