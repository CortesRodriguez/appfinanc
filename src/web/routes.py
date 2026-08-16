"""Modulo Presentador: rutas del Controlador Web (RF-07 a RF-15, CU-01 a CU-10)."""

import json
import os
import time
import uuid
from datetime import datetime, timezone

from flask import Blueprint, Response, current_app, jsonify, render_template, request, session
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from src.extensions import db
from src.extractor import ExtractionError, VALID_PERIODS, get_indicator, get_macro_indicators, get_price_series, get_quotes
from src.nlp import generate_explanation, regenerate_explanation, validate_coherence
from src.nlp.glossary import list_terms, search_terms
from src.evaluation.models import CoherenceCheck, InstrumentVisit, QueryLog
from src.evaluation import ensure_evaluation_session, surveys
from src.evaluation.reports import build_comparative_report, export_report_csv
from src.profile.service import get_detail_level
from src.constants import INDICATOR_LABELS

bp = Blueprint("web", __name__)

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")

with open(os.path.join(_DATA_DIR, "instruments.json"), encoding="utf-8") as f:
    INSTRUMENTS = json.load(f)


def _get_session_id():
    if "sid" not in session:
        session["sid"] = str(uuid.uuid4())
    return session["sid"]


@bp.before_app_request
def _ensure_session_cookie():
    """Establece `session['sid']` antes de que el navegador dispare nada mas.

    El dashboard hace varias llamadas en paralelo al seleccionar un
    instrumento (Promise.all de 4 indicadores + el registro de historial).
    Flask serializa toda la sesion en una sola cookie por respuesta: si
    "sid" todavia no existe, cada una de esas llamadas concurrentes puede
    intentar crearla al mismo tiempo, y la ultima respuesta en aplicarse
    en el navegador pisa a las demas (incluyendo el historial recien
    escrito). Fijar la cookie aqui, en la carga de pagina, evita que
    exista esa ventana de carrera: para cuando el dashboard hace su
    primera llamada por AJAX, la cookie de sesion ya esta establecida.
    """
    _get_session_id()


def _current_user_id():
    """Identidad del usuario si hay una sesion JWT valida, o None (consulta anonima).

    RF-18.1: cuando hay sesion iniciada, la consulta queda asociada a la
    cuenta para construir el perfil de aprendizaje. Sin sesion, el flujo
    de consulta anonima (session_id de Flask) sigue funcionando igual
    que antes de agregar autenticacion.
    """
    try:
        verify_jwt_in_request(optional=True)
    except Exception:  # noqa: BLE001 - token invalido/expirado: se trata como anonimo
        return None

    identity = get_jwt_identity()
    return int(identity) if identity else None




def _push_history(symbol: str, indicator_labels: list, timestamp: str):
    """Registra una consulta en el historial de sesion (RF-10).

    Se llama una unica vez por seleccion de instrumento (ver
    `/api/historial/visita`), nunca desde `/api/query`: ese endpoint lo
    llama el dashboard cuatro veces en paralelo (una por indicador) y
    mezclar el historial ahi generaba una condicion de carrera sobre la
    cookie de sesion (lecturas/escrituras concurrentes se pisaban entre
    si), resultando en mas filas de las esperadas.
    """
    history = session.get("history", [])
    history.insert(0, {"symbol": symbol, "indicators": indicator_labels, "timestamp": timestamp})
    session["history"] = history[: current_app.config["HISTORY_MAX_ITEMS"]]


@bp.route("/")
def index():
    return render_template(
        "index.html",
        instruments=INSTRUMENTS,
        periods=VALID_PERIODS,
        indicators=INDICATOR_LABELS,
    )


@bp.route("/api/instruments")
def api_instruments():
    return jsonify(INSTRUMENTS)


@bp.route("/api/quotes")
def api_quotes():
    """Cotizaciones para el sidebar del dashboard (precio + variacion diaria)."""
    symbols = [inst["symbol"] for inst in INSTRUMENTS]
    quotes = get_quotes(symbols, cache_ttl_seconds=current_app.config["CACHE_TTL_SECONDS"])

    result = []
    for inst in INSTRUMENTS:
        quote = quotes.get(inst["symbol"]) or {}
        result.append(
            {
                "symbol": inst["symbol"],
                "name": inst["name"],
                "type": inst["type"],
                "sector": inst.get("sector", ""),
                "price": quote.get("price"),
                "daily_change_pct": quote.get("daily_change_pct"),
            }
        )
    return jsonify(result)


@bp.route("/api/ticker")
def api_ticker():
    """Cinta de precios: UF, dolar, TPM, IPC (macro) + IPSA y las 30 acciones del catalogo.

    El IPSA ya no forma parte del catalogo seleccionable del dashboard
    (es un indice, no una accion que se pueda consultar individualmente),
    pero se sigue mostrando en la cinta: se pide su cotizacion aparte.
    """
    macro = get_macro_indicators(cache_ttl_seconds=current_app.config["CACHE_TTL_SECONDS"])
    symbols = [inst["symbol"] for inst in INSTRUMENTS] + ["^IPSA"]
    quotes = get_quotes(symbols, cache_ttl_seconds=current_app.config["CACHE_TTL_SECONDS"])

    items = []
    for key in ("ipsa", "uf", "dolar", "tpm", "ipc"):
        if key == "ipsa":
            ipsa_quote = quotes.get("^IPSA") or {}
            items.append(
                {
                    "kind": "macro",
                    "label": "IPSA",
                    "value": ipsa_quote.get("price"),
                    "unit": "pts",
                    "daily_change_pct": ipsa_quote.get("daily_change_pct"),
                }
            )
            continue

        entry = macro.get(key)
        if entry:
            items.append(
                {
                    "kind": "macro",
                    "label": entry["label"],
                    "value": entry["value"],
                    "unit": "$" if key in ("uf", "dolar") else "%",
                    "daily_change_pct": None,
                }
            )

    for inst in INSTRUMENTS:
        quote = quotes.get(inst["symbol"]) or {}
        items.append(
            {
                "kind": "instrument",
                "label": inst["symbol"].replace(".SN", ""),
                "value": quote.get("price"),
                "unit": "$",
                "daily_change_pct": quote.get("daily_change_pct"),
            }
        )

    return jsonify(items)


@bp.route("/api/chart")
def api_chart():
    """Serie de precios + MA50/MA200 para el grafico de tendencia."""
    symbol = request.args.get("symbol", "")
    days = int(request.args.get("days", 365))

    if not symbol:
        return jsonify({"error": "Debes indicar un instrumento."}), 400

    try:
        series = get_price_series(
            symbol,
            days=days,
            alpha_vantage_key=current_app.config["ALPHAVANTAGE_API_KEY"],
            cache_ttl_seconds=current_app.config["CACHE_TTL_SECONDS"],
        )
    except ExtractionError as exc:
        return jsonify({"error": str(exc)}), 502

    return jsonify(series)


@bp.route("/api/lookup")
def api_lookup():
    """Busqueda de un instrumento fuera del catalogo acotado, por ticker exacto."""
    symbol = request.args.get("symbol", "").strip().upper()
    if not symbol:
        return jsonify({"error": "Debes escribir un ticker para buscar."}), 400

    try:
        get_price_series(
            symbol,
            days=90,
            alpha_vantage_key=current_app.config["ALPHAVANTAGE_API_KEY"],
            cache_ttl_seconds=current_app.config["CACHE_TTL_SECONDS"],
        )
    except ExtractionError:
        return jsonify({"error": f"No se encontraron datos para el ticker '{symbol}'."}), 404

    return jsonify({"symbol": symbol, "name": symbol, "type": "Personalizado", "sector": ""})


@bp.route("/api/historial/visita", methods=["POST"])
def api_log_visit():
    """Registra en el historial (RF-10) la seleccion de un instrumento en el dashboard.

    El dashboard llama esto una sola vez por instrumento seleccionado,
    separado de las cuatro llamadas paralelas a `/api/query` (una por
    indicador) para evitar la condicion de carrera descrita en `_push_history`.
    """
    payload = request.get_json(silent=True) or {}
    symbol = payload.get("symbol", "")
    if not symbol:
        return jsonify({"error": "Debes indicar un instrumento."}), 400

    _push_history(symbol, list(INDICATOR_LABELS.values()), datetime.now(timezone.utc).isoformat())

    # RF-19.2/RF-19.3: si hay sesion iniciada, esta es la unica escritura
    # que representa "el usuario vio este instrumento" para el perfil de
    # aprendizaje (a diferencia de QueryLog, que registra cada uno de los
    # cuatro indicadores consultados en paralelo por separado).
    user_id = _current_user_id()
    if user_id:
        db.session.add(InstrumentVisit(user_id=user_id, instrument=symbol))
        db.session.commit()

    return jsonify({"ok": True})


def _run_query(symbol, indicator, days, variant=0, detail_level="estandar"):
    started = time.perf_counter()
    indicator_data = get_indicator(
        symbol,
        indicator,
        days=days,
        alpha_vantage_key=current_app.config["ALPHAVANTAGE_API_KEY"],
        cache_ttl_seconds=current_app.config["CACHE_TTL_SECONDS"],
    )
    explanation = generate_explanation(
        indicator_data, variant=variant, use_finbert=current_app.config["USE_FINBERT"], detail_level=detail_level
    )
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return indicator_data, explanation, elapsed_ms


def _log_and_validate(session_id, symbol, indicator, indicator_data, explanation, elapsed_ms, user_id=None, is_regeneration=False):
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
        )
    )

    coherent, reason = validate_coherence(indicator_data, explanation["text"])
    db.session.add(
        CoherenceCheck(
            session_id=session_id,
            instrument=symbol,
            indicator=indicator,
            value=indicator_data["value"],
            risk_level=indicator_data["risk_level"],
            explanation_text=explanation["text"],
            coherent=coherent,
            reason=reason,
            status="pendiente" if not coherent else "revisado",
        )
    )
    db.session.commit()
    return coherent, reason


@bp.route("/api/query", methods=["POST"])
def api_query():
    payload = request.get_json(silent=True) or {}
    symbol = payload.get("symbol", "")
    indicator = payload.get("indicator", "")
    days = int(payload.get("days", 90))

    session_id = _get_session_id()
    ensure_evaluation_session(session_id)
    user_id = _current_user_id()
    detail_level = get_detail_level(user_id, indicator) if user_id else "estandar"

    try:
        indicator_data, explanation, elapsed_ms = _run_query(symbol, indicator, days, variant=0, detail_level=detail_level)
    except ExtractionError as exc:
        # RF-09.1: mensaje de error comprensible cuando no se puede obtener el indicador
        return jsonify({"error": str(exc)}), 502

    coherent, reason = _log_and_validate(
        session_id, symbol, indicator, indicator_data, explanation, elapsed_ms, user_id=user_id, is_regeneration=False
    )

    return jsonify(
        {
            "symbol": symbol,
            "indicator": indicator,
            "indicator_label": INDICATOR_LABELS.get(indicator, indicator),
            "value": indicator_data["value"],
            "unit": indicator_data["unit"],
            "risk_level": indicator_data["risk_level"],
            "source": indicator_data["source"],
            "extracted_at": indicator_data["extracted_at"],
            "processing_time_ms": elapsed_ms,
            "explanation": explanation["text"],
            "variant": explanation["variant"],
            "coherent": coherent,
            "readability_score": explanation["readability_score"],
            "trend": indicator_data.get("trend"),
        }
    )


@bp.route("/api/regenerate", methods=["POST"])
def api_regenerate():
    payload = request.get_json(silent=True) or {}
    symbol = payload.get("symbol", "")
    indicator = payload.get("indicator", "")
    days = int(payload.get("days", 90))
    previous_variant = int(payload.get("previous_variant", 0))

    session_id = _get_session_id()
    user_id = _current_user_id()
    detail_level = get_detail_level(user_id, indicator) if user_id else "estandar"

    try:
        started = time.perf_counter()
        indicator_data = get_indicator(
            symbol,
            indicator,
            days=days,
            alpha_vantage_key=current_app.config["ALPHAVANTAGE_API_KEY"],
            cache_ttl_seconds=current_app.config["CACHE_TTL_SECONDS"],
        )
        explanation = regenerate_explanation(
            indicator_data, previous_variant, use_finbert=current_app.config["USE_FINBERT"], detail_level=detail_level
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
    except ExtractionError as exc:
        return jsonify({"error": str(exc)}), 502

    coherent, reason = _log_and_validate(
        session_id, symbol, indicator, indicator_data, explanation, elapsed_ms, user_id=user_id, is_regeneration=True
    )

    same_as_before = explanation["variant"] == previous_variant
    return jsonify(
        {
            "symbol": symbol,
            "indicator": indicator,
            "indicator_label": INDICATOR_LABELS.get(indicator, indicator),
            "value": indicator_data["value"],
            "unit": indicator_data["unit"],
            "risk_level": indicator_data["risk_level"],
            "trend": indicator_data.get("trend"),
            "explanation": explanation["text"],
            "variant": explanation["variant"],
            "coherent": coherent,
            "unchanged": same_as_before,  # Excepcion 1 de CU-04
        }
    )


@bp.route("/history")
def history():
    return render_template("history.html", history=session.get("history", []))


@bp.route("/glosario")
def glossary_page():
    return render_template("glossary.html", terms=list_terms())


@bp.route("/api/glosario/buscar")
def api_glossary_search():
    query = request.args.get("q", "")
    return jsonify(search_terms(query))


@bp.route("/encuesta/<phase>", methods=["GET"])
def survey_page(phase):
    if phase not in ("pre", "post"):
        return "Fase de encuesta invalida", 404

    session_id = _get_session_id()
    if phase == "post" and not surveys.has_completed_phase(session_id, "pre"):
        # Excepcion 1, CU-07: no completo pre-test previamente
        return render_template("survey.html", phase=phase, questions=[], blocked=True)

    already_done = surveys.has_completed_phase(session_id, phase)
    return render_template(
        "survey.html", phase=phase, questions=surveys.get_questions(), blocked=False, already_done=already_done
    )


@bp.route("/api/encuesta/<phase>", methods=["POST"])
def api_survey_submit(phase):
    if phase not in ("pre", "post"):
        return jsonify({"error": "Fase invalida"}), 400

    session_id = _get_session_id()

    if phase == "post" and not surveys.has_completed_phase(session_id, "pre"):
        return jsonify({"error": "Debes completar la encuesta pre-test antes de responder el post-test."}), 409

    answers = request.get_json(silent=True) or {}
    score, total, missing = surveys.submit_survey(session_id, phase, answers)

    if missing:
        return jsonify({"error": "Faltan preguntas por responder.", "missing": missing}), 400

    result = {"score": score, "total": total}

    if phase == "post":
        pre_score = surveys.get_score(session_id, "pre")
        if pre_score:
            result["pre_score"] = pre_score["correct"]
            result["delta"] = score - pre_score["correct"]

    return jsonify(result)


@bp.route("/admin/coherencia")
def admin_coherence():
    status_filter = request.args.get("status", "todos")
    query = CoherenceCheck.query.order_by(CoherenceCheck.created_at.desc())
    if status_filter in ("pendiente", "revisado"):
        query = query.filter_by(status=status_filter)
    checks = query.limit(200).all()
    return render_template("admin_coherence.html", checks=checks, status_filter=status_filter)


@bp.route("/admin/coherencia/<int:check_id>/revisar", methods=["POST"])
def admin_coherence_review(check_id):
    check = CoherenceCheck.query.get_or_404(check_id)
    check.status = "revisado"
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/admin/reporte")
def admin_report():
    report = build_comparative_report()
    return render_template("admin_report.html", report=report)


@bp.route("/admin/reporte/exportar.csv")
def admin_report_export():
    csv_content = export_report_csv()
    return Response(
        csv_content,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=reporte_comprension.csv"},
    )
