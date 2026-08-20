"""Modulo Presentador: rutas del Controlador Web (RF-07 a RF-15, CU-01 a CU-10)."""

import json
import math
import os
import time
import uuid
from datetime import datetime, timezone

from flask import Blueprint, Response, current_app, jsonify, render_template, request, session
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from src.auth.models import User
from src.extensions import db
from src.extractor import ExtractionError, VALID_PERIODS, get_indicator, get_macro_indicators, get_price_series, get_quotes
from src.nlp import generate_explanation, regenerate_explanation, validate_coherence
from src.nlp.glossary import list_terms, search_terms
from src.evaluation.models import CoherenceCheck, InstrumentVisit, QueryLog
from src.evaluation import ensure_evaluation_session, surveys
from src.evaluation.eligibility import is_eligible_for_survey
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
    """Registra una visita al instrumento en la sesion (RF-10).

    Se llama una unica vez por seleccion de instrumento (ver
    `/api/historial/visita`). Antes se le llamaba desde `/api/query`, pero
    el dashboard ahora golpea `/api/query` unicamente cuando la usuaria
    pulsa "Ver explicacion en simple" en una card — ver `_push_query`.
    """
    history = session.get("history", [])
    history.insert(0, {"symbol": symbol, "indicators": indicator_labels, "timestamp": timestamp})
    session["history"] = history[: current_app.config["HISTORY_MAX_ITEMS"]]


def _push_query(entry: dict):
    """Registra en la sesion una consulta de explicacion (RF-02.2 / CU-03).

    A diferencia de `_push_history` (que registra visitas al instrumento
    para RF-10), este historial guarda una fila POR consulta explicita de
    un indicador — es la unidad de trazabilidad de RF-02.2: incluye el
    nombre literal del indicador, la fuente (Yahoo/Alpha Vantage), la
    ventana pedida, la marca de extraccion del dato y la marca de consulta.

    Se muestra en `/history` como tabla legible.
    """
    queries = session.get("queries", [])
    queries.insert(0, entry)
    session["queries"] = queries[: current_app.config["HISTORY_MAX_ITEMS"]]


# Meses en espanol para formateo "13:25:45 - 28 de agosto de 2026" sin
# depender de la locale del sistema (que en macOS/Linux es inconsistente).
_MONTHS_ES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
    7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}

# La app se usa desde Chile: guardamos las marcas de tiempo en UTC (ISO)
# para portabilidad, pero al renderizarlas en /history las convertimos a
# hora local (America/Santiago = UTC-4 invierno / UTC-3 verano, con
# transiciones DST manejadas por zoneinfo). Es lo que hace que la fila
# diga "15:24:30" cuando el reloj local marca 15:24:30, no la hora UTC.
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
    _CHILE_TZ = ZoneInfo("America/Santiago")
except Exception:  # noqa: BLE001 - fallback si tzdata no esta disponible
    _CHILE_TZ = timezone.utc


def _format_datetime_es(iso: str) -> str:
    """Convierte una fecha ISO (UTC) al formato de RF-02.2 en hora local
    chilena: `HH:MM:SS - dd de mes de yyyy`. Se aplica en el template del
    historial de consultas via el filtro Jinja `es_datetime`.
    """
    if not iso:
        return "—"
    try:
        raw = iso.replace("Z", "+00:00") if isinstance(iso, str) else iso
        dt_obj = datetime.fromisoformat(raw) if isinstance(raw, str) else raw
    except (ValueError, TypeError):
        return str(iso)
    # Si el timestamp no trae tz (naive), asumimos UTC — es lo que produce
    # `datetime.now(timezone.utc)` cuando se serializa con isoformat() sin +00:00.
    if dt_obj.tzinfo is None:
        dt_obj = dt_obj.replace(tzinfo=timezone.utc)
    local = dt_obj.astimezone(_CHILE_TZ)
    return f"{local:%H:%M:%S} - {local.day} de {_MONTHS_ES[local.month]} de {local.year}"


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
    interval = request.args.get("interval", "1d")

    if not symbol:
        return jsonify({"error": "Debes indicar un instrumento."}), 400

    try:
        series = get_price_series(
            symbol,
            days=days,
            interval=interval,
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
    # Guardarrail: si el valor del indicador es NaN (por precios huecos en la
    # fuente) el INSERT en coherence_checks fallaba con NOT NULL constraint y
    # Flask devolvia HTML 500 al frontend ("Unexpected token '<'"). Se ataca
    # tambien en `_to_series` y `_fetch_yahoo`; esta es la ultima defensa antes
    # de tocar la BD, y ademas convierte el NaN en un ExtractionError amigable
    # que el JS ya sabe mostrar como banner.
    val = indicator_data.get("value")
    if val is None or (isinstance(val, float) and math.isnan(val)):
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
        coherent, reason = _log_and_validate(
            session_id, symbol, indicator, indicator_data, explanation, elapsed_ms, user_id=user_id, is_regeneration=False
        )
    except ExtractionError as exc:
        # RF-09.1: mensaje de error comprensible cuando no se puede obtener el indicador.
        # Tambien atrapa el guardarrail de _log_and_validate cuando el valor viene NaN.
        db.session.rollback()
        return jsonify({"error": str(exc)}), 502

    # RF-02.2 / CU-03: la consulta explicita queda registrada en la sesion
    # con toda la info de trazabilidad, para mostrarla en /history.
    _push_query(
        {
            "symbol": symbol,
            "indicator": indicator,
            "indicator_label": INDICATOR_LABELS.get(indicator, indicator),
            "value": indicator_data["value"],
            "unit": indicator_data["unit"],
            "risk_level": indicator_data["risk_level"],
            "source": indicator_data["source"],
            "extracted_at": indicator_data["extracted_at"],
            "consulted_at": datetime.now(timezone.utc).isoformat(),
            "period_days": indicator_data.get("period_days", days),
            "coherent": coherent,
        }
    )

    # Instrumento 1: señalar al frontend si esta cuenta consintió al
    # registrarse (acepta_evaluacion=True) Y ya cumplió el umbral de
    # exposición. En ese caso el banner del dashboard invita a responder la
    # encuesta retrospectiva. Los usuarios sin consentimiento no ven nada.
    invitacion_estudio = None
    if user_id and is_eligible_for_survey(user_id):
        user = db.session.get(User, user_id)
        if user and user.acepta_evaluacion is True:
            invitacion_estudio = "mostrar"

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
            "signal": indicator_data.get("signal"),
            "invitacion_estudio": invitacion_estudio,
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
        coherent, reason = _log_and_validate(
            session_id, symbol, indicator, indicator_data, explanation, elapsed_ms, user_id=user_id, is_regeneration=True
        )
    except ExtractionError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 502

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
            "signal": indicator_data.get("signal"),
            "explanation": explanation["text"],
            "variant": explanation["variant"],
            "coherent": coherent,
            "unchanged": same_as_before,  # Excepcion 1 de CU-04
        }
    )


@bp.route("/api/indicador/valor")
def api_indicator_value():
    """Version ligera y sin traza para el fetch inicial del dashboard.

    A diferencia de /api/query, este endpoint NO genera explicacion, NO corre
    FinBERT y NO escribe en `query_logs` ni `coherence_checks`. Solo calcula
    el valor del indicador (usa el mismo cache TTL de precios) y lo devuelve.

    El objetivo es soportar el flujo "explicaciones bajo demanda" del
    dashboard (RF-02.2 / CU-03): al hacer click en una accion se cargan los
    4 valores rapido con este endpoint; cada QueryLog persistido corresponde
    a un click posterior en el boton "Ver explicacion en simple" de una card,
    dandole semantica real a la traza — es una consulta deliberada, no un
    batch automatico.
    """
    symbol = request.args.get("symbol", "")
    indicator = request.args.get("indicator", "")
    try:
        days = int(request.args.get("days", 90))
    except (TypeError, ValueError):
        return jsonify({"error": "Parametro 'days' invalido."}), 400

    if not symbol or not indicator:
        return jsonify({"error": "Debes indicar 'symbol' e 'indicator'."}), 400

    try:
        data = get_indicator(
            symbol,
            indicator,
            days=days,
            alpha_vantage_key=current_app.config["ALPHAVANTAGE_API_KEY"],
            cache_ttl_seconds=current_app.config["CACHE_TTL_SECONDS"],
        )
    except ExtractionError as exc:
        return jsonify({"error": str(exc)}), 502

    val = data.get("value")
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return jsonify({"error": "No hay datos suficientes para calcular este indicador."}), 502

    return jsonify(
        {
            "symbol": symbol,
            "indicator": indicator,
            "indicator_label": INDICATOR_LABELS.get(indicator, indicator),
            "value": data["value"],
            "unit": data["unit"],
            "risk_level": data["risk_level"],
            "source": data["source"],
            "extracted_at": data["extracted_at"],
            "period_days": data["period_days"],
            "trend": data.get("trend"),
            "signal": data.get("signal"),
        }
    )


@bp.route("/history")
def history():
    return render_template(
        "history.html",
        queries=session.get("queries", []),
        visits=session.get("history", []),
    )


@bp.route("/glosario")
def glossary_page():
    return render_template("glossary.html", terms=list_terms())


@bp.route("/api/glosario/buscar")
def api_glossary_search():
    query = request.args.get("q", "")
    return jsonify(search_terms(query))


@bp.route("/encuesta", methods=["GET"])
def survey_page():
    """Instrumento 1 — Autoevaluación Retrospectiva.

    Requiere que la persona (a) esté autenticada, (b) haya alcanzado el
    umbral de exposición (`SURVEY_THRESHOLD` visitas) y (c) haya consentido
    participar. Si algo falla, se redirige al dashboard con motivo.
    """
    user_id = _current_user_id()
    if not user_id:
        return render_template("survey.html", concepts=[], blocked_reason="anonimo")

    if not is_eligible_for_survey(user_id):
        return render_template("survey.html", concepts=[], blocked_reason="umbral")

    user = db.session.get(User, user_id)
    if not user or user.acepta_evaluacion is not True:
        return render_template("survey.html", concepts=[], blocked_reason="sin_consentimiento")

    return render_template("survey.html", concepts=surveys.get_concepts(), blocked_reason=None)


@bp.route("/api/encuesta", methods=["POST"])
def api_survey_submit():
    """Recibe la autoevaluación retrospectiva y la persiste de forma anónima.

    La respuesta se guarda con un `response_token` nuevo, sin `user_id`
    ni `session_id`. Aunque este endpoint verifica que la persona haya
    consentido, ese chequeo se hace SOLO para autorización — el `user_id`
    no se propaga a la fila persistida (`surveys.submit_survey` no lo
    acepta como parámetro por diseño).
    """
    user_id = _current_user_id()
    if not user_id:
        return jsonify({"error": "Debes iniciar sesión para responder la encuesta."}), 403

    if not is_eligible_for_survey(user_id):
        return jsonify({"error": "La encuesta se habilita después de al menos 5 consultas."}), 403

    user = db.session.get(User, user_id)
    if not user or user.acepta_evaluacion is not True:
        return jsonify({"error": "No has aceptado participar en el estudio."}), 403

    answers = request.get_json(silent=True) or {}
    try:
        result = surveys.submit_survey(answers)
    except surveys.SurveyValidationError as exc:
        return jsonify({"error": str(exc)}), 400

    if "missing" in result:
        return jsonify({"error": "Faltan conceptos por responder.", "missing": result["missing"]}), 400

    return jsonify(result)


@bp.route("/api/evaluacion/consentimiento", methods=["POST"])
def api_evaluation_consent():
    """Registra la decisión de la persona sobre participar en el estudio.

    Payload: `{ "acepta": true|false }`. Solo modifica `User.acepta_evaluacion`,
    nada más. La respuesta incluye la URL a la encuesta cuando `acepta=true`,
    para que el frontend redirija sin necesidad de otro round-trip.
    """
    user_id = _current_user_id()
    if not user_id:
        return jsonify({"error": "Debes iniciar sesión."}), 403

    payload = request.get_json(silent=True) or {}
    acepta = payload.get("acepta")
    if not isinstance(acepta, bool):
        return jsonify({"error": "Debes indicar 'acepta' como true o false."}), 400

    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "Cuenta no encontrada."}), 404

    user.acepta_evaluacion = acepta
    db.session.commit()

    response = {"acepta_evaluacion": user.acepta_evaluacion}
    if acepta:
        response["redirect"] = "/encuesta"
    return jsonify(response)


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
