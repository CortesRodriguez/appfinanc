"""Modulo Presentador: rutas del Controlador Web (RF-07 a RF-10, CU-01 a CU-05)."""

import json
import math
import os
import time
import uuid
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, session, url_for
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from src.extensions import db
from src.extractor import MAX_SYMBOL_LENGTH, ExtractionError, VALID_PERIODS, get_company_news, get_indicator, get_macro_indicators, get_market_news, get_price_series, get_quotes
from src.nlp import generate_explanation, regenerate_explanation, validate_coherence
from src.nlp.glossary import list_terms, search_terms
from src.evaluation.models import InstrumentVisit, QueryLog
from src.nlp.levels import DEFAULT_LEVEL
from src.profile.service import get_detail_level, preferred_variant, recent_visits
from src.constants import INDICATOR_LABELS

bp = Blueprint("web", __name__)

SPARKLINE_POINTS = 30

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")

try:
    with open(os.path.join(_DATA_DIR, "instruments.json"), encoding="utf-8") as f:
        INSTRUMENTS = json.load(f)
except FileNotFoundError:
    INSTRUMENTS = []


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




# Meses en espanol para formateo "13:25:45 - 28 de agosto de 2026" sin
# depender de la locale del sistema (que en macOS/Linux es inconsistente).
_MONTHS_ES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
    7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}

# La app se usa desde Chile: guardamos las marcas de tiempo en UTC (ISO)
# para portabilidad, pero al renderizarlas en el historial del perfil las convertimos a
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
    # Portada: "Sigue donde quedaste" solo existe con cuenta (el historial es por usuario).
    user_id = _current_user_id()
    recent_stocks = []
    if user_id:
        recent_stocks = [
            {"symbol": v["instrument"], "name": _resolve_display_name(v["instrument"])}
            for v in recent_visits(user_id, limit=5)
        ]
    return render_template(
        "index.html",
        instruments=INSTRUMENTS,
        periods=VALID_PERIODS,
        indicators=INDICATOR_LABELS,
        recent_stocks=recent_stocks,
    )


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


@bp.route("/api/news")
def api_news():
    """Noticias de la portada: del mercado, o de una empresa del catalogo con ?symbol=.

    El texto de busqueda sale del catalogo (alias), nunca del usuario: un
    simbolo fuera de INSTRUMENTS responde 404. Si la fuente externa falla,
    responde 200 con `items: []` para que el frontend muestre el estado vacio.
    """
    ttl = current_app.config["NEWS_CACHE_TTL_SECONDS"]
    max_items = current_app.config["NEWS_MAX_ITEMS"]
    symbol = request.args.get("symbol", "").strip()
    if not symbol:
        return jsonify({"items": get_market_news(max_items, ttl)})

    inst = next((i for i in INSTRUMENTS if i["symbol"] == symbol), None)
    if inst is None:
        return jsonify({"error": "Instrumento no encontrado en el catálogo."}), 404
    return jsonify({"items": get_company_news(inst, max_items, ttl)})


@bp.route("/api/sparkline")
def api_sparkline():
    """Ultimos cierres de una accion del catalogo para el mini-grafico de la portada.

    Usa la misma serie cacheada que /api/chart (no hay otra descarga), pero
    devuelve solo SPARKLINE_POINTS valores en vez de ~10 anos de historia.
    """
    symbol = request.args.get("symbol", "").strip()
    if not any(i["symbol"] == symbol for i in INSTRUMENTS):
        return jsonify({"error": "Instrumento no encontrado en el catálogo."}), 404
    try:
        series = get_price_series(
            symbol,
            days=30,
            alpha_vantage_key=current_app.config["ALPHAVANTAGE_API_KEY"],
            cache_ttl_seconds=current_app.config["CACHE_TTL_SECONDS"],
        )
    except ExtractionError as exc:
        return jsonify({"error": str(exc)}), 502
    return jsonify({"symbol": symbol, "closes": series["close"][-SPARKLINE_POINTS:]})


@bp.route("/api/chart")
def api_chart():
    """Serie de precios + MA50/MA200 para el grafico de tendencia."""
    symbol = request.args.get("symbol", "")
    try:
        days = int(request.args.get("days", 365))
    except (TypeError, ValueError):
        return jsonify({"error": "Parametro 'days' invalido."}), 400
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
    if len(symbol) > MAX_SYMBOL_LENGTH:
        return jsonify({"error": f"El ticker no puede superar los {MAX_SYMBOL_LENGTH} caracteres."}), 400

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
    """Registra la seleccion de un instrumento en el dashboard (RF-10, RF-19.2).

    El dashboard llama esto una sola vez por instrumento seleccionado,
    separado de `/api/query` (que solo se llama al pedir una explicacion).
    Sin sesion iniciada no se guarda nada: el historial es de la cuenta.
    """
    payload = request.get_json(silent=True) or {}
    symbol = payload.get("symbol", "")
    if not symbol:
        return jsonify({"error": "Debes indicar un instrumento."}), 400
    if not isinstance(symbol, str) or len(symbol) > MAX_SYMBOL_LENGTH:
        return jsonify({"error": "Instrumento invalido."}), 400

    # RF-19.2/RF-19.3: si hay sesion iniciada, esta es la unica escritura
    # que representa "el usuario vio este instrumento" para el perfil de
    # aprendizaje (a diferencia de QueryLog, que registra cada uno de los
    # cuatro indicadores consultados en paralelo por separado).
    user_id = _current_user_id()
    if user_id:
        db.session.add(InstrumentVisit(user_id=user_id, instrument=symbol))
        db.session.commit()

    return jsonify({"ok": True})


def _resolve_display_name(symbol: str) -> str:
    """Nombre de empresa para el ticker dado, o el ticker limpio como fallback."""
    return next(
        (inst["name"] for inst in INSTRUMENTS if inst["symbol"] == symbol),
        symbol.replace(".SN", ""),
    )


def _run_query(symbol, indicator, days, variant=0, detail_level=DEFAULT_LEVEL):
    started = time.perf_counter()
    indicator_data = get_indicator(
        symbol,
        indicator,
        days=days,
        alpha_vantage_key=current_app.config["ALPHAVANTAGE_API_KEY"],
        cache_ttl_seconds=current_app.config["CACHE_TTL_SECONDS"],
    )
    explanation = generate_explanation(
        indicator_data,
        variant=variant,
        use_finbert=current_app.config["USE_FINBERT"],
        detail_level=detail_level,
        display_name=_resolve_display_name(symbol),
        use_llm=current_app.config.get("USE_LLM", False),
        llm_api_key=current_app.config.get("GROQ_API_KEY", ""),
    )
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return indicator_data, explanation, elapsed_ms


def _log_and_validate(session_id, symbol, indicator, indicator_data, explanation, elapsed_ms, user_id=None, is_regeneration=False):
    # Guardarrail: si el valor del indicador es NaN (por precios huecos en la
    # fuente) Flask devolvia HTML 500 al frontend ("Unexpected token '<'").
    # Se ataca tambien en `_to_series` y `_fetch_yahoo`; esta es la ultima
    # defensa antes de tocar la BD, y ademas convierte el NaN en un ExtractionError amigable
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
            value=indicator_data["value"],
            unit=indicator_data.get("unit"),
            risk_level=indicator_data.get("risk_level"),
            period_days=indicator_data.get("period_days"),
        )
    )

    db.session.commit()
    coherent, reason = validate_coherence(indicator_data, explanation["text"])
    return coherent, reason


@bp.route("/api/query", methods=["POST"])
def api_query():
    payload = request.get_json(silent=True) or {}
    symbol = payload.get("symbol", "")
    indicator = payload.get("indicator", "")
    days = int(payload.get("days", 90))

    session_id = _get_session_id()
    user_id = _current_user_id()
    detail_level = get_detail_level(user_id, indicator) if user_id else DEFAULT_LEVEL
    # RF-13.2: la consulta parte en la redaccion en la que este usuario suele quedarse.
    variant = (preferred_variant(user_id, indicator) or 0) if user_id else 0

    try:
        indicator_data, explanation, elapsed_ms = _run_query(symbol, indicator, days, variant=variant, detail_level=detail_level)
        coherent, reason = _log_and_validate(
            session_id, symbol, indicator, indicator_data, explanation, elapsed_ms, user_id=user_id, is_regeneration=False
        )
    except ExtractionError as exc:
        # RF-09.1: mensaje de error comprensible cuando no se puede obtener el indicador.
        # Tambien atrapa el guardarrail de _log_and_validate cuando el valor viene NaN.
        db.session.rollback()
        return jsonify({"error": str(exc)}), 502

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
            "detail_level": explanation["detail_level"],
            "coherent": coherent,
            "readability_score": explanation["readability_score"],
            "finbert_signal": explanation.get("finbert_signal"),
            "trend": indicator_data.get("trend"),
            "signal": indicator_data.get("signal"),
        }
    )


@bp.route("/api/regenerate", methods=["POST"])
def api_regenerate():
    payload = request.get_json(silent=True) or {}
    symbol = payload.get("symbol", "")
    indicator = payload.get("indicator", "")
    try:
        days = int(payload.get("days", 90))
        previous_variant = int(payload.get("previous_variant", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Parametro 'days' o 'previous_variant' invalido."}), 400

    session_id = _get_session_id()
    user_id = _current_user_id()
    detail_level = get_detail_level(user_id, indicator) if user_id else DEFAULT_LEVEL

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
            indicator_data, previous_variant,
            use_finbert=current_app.config["USE_FINBERT"],
            detail_level=detail_level,
            display_name=_resolve_display_name(symbol),
            use_llm=current_app.config.get("USE_LLM", False),
            llm_api_key=current_app.config.get("GROQ_API_KEY", ""),
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
            "detail_level": explanation["detail_level"],
            "coherent": coherent,
            "finbert_signal": explanation.get("finbert_signal"),
            "unchanged": same_as_before,  # Excepcion 1 de CU-04
        }
    )


@bp.route("/api/indicador/valor")
def api_indicator_value():
    """Version ligera y sin traza para el fetch inicial del dashboard.

    A diferencia de /api/query, este endpoint NO genera explicacion, NO corre
    FinBERT y NO escribe en `query_logs`. Solo calcula
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
    # El historial vive en la cuenta (pestana de /perfil); se conserva la URL antigua.
    return redirect(url_for("profile.profile_page") + "#historial")


@bp.route("/glosario")
def glossary_page():
    return render_template("glossary.html", terms=list_terms())


@bp.route("/api/glosario/buscar")
def api_glossary_search():
    query = request.args.get("q", "")
    category = request.args.get("category", "")
    return jsonify(search_terms(query, category=category))


