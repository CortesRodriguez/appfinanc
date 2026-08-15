"""Blueprint principal del Presentador (Sprint 7).

Cubre las rutas del prototipo:
- /           : selector de instrumento + rango + indicador + resultado
- /cinta      : endpoint AJAX con los datos macro (RF-07.3, RF-07.4)
- /consulta   : POST que dispara el pipeline y renderiza la explicacion
- /regenerar  : RF-06.2
- /historial  : RF-10.1 (ultimas 5 consultas en la sesion)
- /glosario   : RF-09.2
"""

from __future__ import annotations

import logging
from datetime import datetime

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_jwt_extended import get_jwt_identity, jwt_required

from extractor.yahoo_extractor import (
    InstrumentoNoSoportadoError,
    RangoNoSoportadoError,
)
from nlp_processor import GLOSARIO, buscar_termino

from .extensions import db
from .models import Consulta, Usuario
from .services import ServicioConsulta

bp = Blueprint("main", __name__)
_LOG = logging.getLogger("app.main")
_servicio: ServicioConsulta | None = None


def _get_servicio() -> ServicioConsulta:
    global _servicio
    if _servicio is None:
        _servicio = ServicioConsulta()
    return _servicio


def _usuario_actual() -> Usuario | None:
    ident = get_jwt_identity()
    if not ident:
        return None
    return db.session.get(Usuario, int(ident))


def _agregar_historial(entrada: dict) -> None:
    historial = session.get("historial", [])
    historial.insert(0, entrada)
    session["historial"] = historial[: current_app.config["HISTORIAL_MAX"]]


# ----------------------------------------------------------------------
# Vistas
# ----------------------------------------------------------------------
@bp.route("/")
@jwt_required(optional=True)
def index():
    usuario = _usuario_actual()
    servicio = _get_servicio()
    return render_template(
        "index.html",
        usuario=usuario,
        tickers=servicio.tickers,
        rangos=servicio.rangos,
        indicadores=servicio.indicadores,
        historial=session.get("historial", []),
    )


@bp.route("/cinta")
@jwt_required(optional=True)
def cinta():
    try:
        datos = _get_servicio().cinta_precios()
    except Exception as exc:  # noqa: BLE001 (RNF-09.1)
        _LOG.warning("cinta fallo: %s", exc)
        return jsonify({"error": True, "mensaje": "No pudimos actualizar la cinta ahora. Reintentaremos pronto."})
    return jsonify(datos)


@bp.route("/consulta", methods=["POST"])
@jwt_required()
def consulta():
    usuario = _usuario_actual()
    if usuario is None:
        return redirect(url_for("auth.login"))

    ticker = request.form.get("ticker", "").strip()
    rango = request.form.get("rango", "").strip()
    indicador = request.form.get("indicador", "").strip()

    servicio = _get_servicio()
    try:
        explicacion, datos = servicio.consultar(usuario, ticker, indicador, rango)
    except InstrumentoNoSoportadoError as exc:
        flash(str(exc), "error")
        return redirect(url_for("main.index"))
    except RangoNoSoportadoError as exc:
        flash(str(exc), "error")
        return redirect(url_for("main.index"))
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("main.index"))
    except Exception as exc:  # noqa: BLE001 (RF-09.1)
        _LOG.exception("fallo en consulta")
        flash(
            "No pudimos completar la consulta. Reintenta en unos minutos.",
            "error",
        )
        return redirect(url_for("main.index"))

    _agregar_historial({
        "ticker": ticker,
        "indicador": indicador,
        "rango": rango,
        "fecha_hora": datetime.utcnow().isoformat(timespec="seconds"),
        "consulta_id": explicacion.metadata.get("consulta_id"),
    })

    return render_template(
        "consulta.html",
        usuario=usuario,
        explicacion=explicacion,
        datos=datos,
        historial=session.get("historial", []),
    )


@bp.route("/regenerar/<int:consulta_id>", methods=["POST"])
@jwt_required()
def regenerar(consulta_id: int):
    usuario = _usuario_actual()
    if usuario is None:
        return redirect(url_for("auth.login"))

    servicio = _get_servicio()
    try:
        explicacion = servicio.regenerar(usuario, consulta_id)
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("main.index"))

    consulta_bd = db.session.get(Consulta, consulta_id)
    return render_template(
        "consulta.html",
        usuario=usuario,
        explicacion=explicacion,
        datos=None,
        historial=session.get("historial", []),
        aviso=(
            "Aqui tienes una explicacion alternativa para el mismo indicador. "
            "Si sigue sin quedar clara, revisa el glosario."
        ),
        consulta_bd=consulta_bd,
    )


@bp.route("/historial")
@jwt_required()
def historial():
    return render_template(
        "historial.html",
        usuario=_usuario_actual(),
        historial=session.get("historial", []),
    )


@bp.route("/glosario")
@jwt_required(optional=True)
def glosario():
    consulta_txt = request.args.get("q", "").strip()
    if consulta_txt:
        resultados = buscar_termino(consulta_txt)
    else:
        resultados = list(GLOSARIO.items())
    return render_template(
        "glosario.html",
        usuario=_usuario_actual(),
        consulta=consulta_txt,
        resultados=resultados,
    )
