"""Blueprint del perfil de aprendizaje (RF-14).

Muestra el indicador mas regenerado, los instrumentos mas consultados,
el total de consultas y la explicacion adaptada para el indicador
que le resulto mas dificil al usuario. Cuando el usuario alcanza el
umbral (5 consultas) y dio su consentimiento, se le ofrece una unica
encuesta anonima.
"""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_jwt_extended import get_jwt_identity, jwt_required

from .extensions import db
from .models import RespuestaEncuesta, Usuario
from .services import ServicioConsulta

bp = Blueprint("perfil", __name__, url_prefix="/perfil")
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


@bp.route("/")
@jwt_required()
def index():
    usuario = _usuario_actual()
    if usuario is None:
        return redirect(url_for("auth.login"))
    resumen = _get_servicio().resumen_perfil(usuario)
    return render_template("perfil.html", usuario=usuario, resumen=resumen)


@bp.route("/encuesta", methods=["GET", "POST"])
@jwt_required()
def encuesta():
    usuario = _usuario_actual()
    if usuario is None:
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        preguntas = {
            "comprension_antes": request.form.get("comprension_antes", ""),
            "comprension_ahora": request.form.get("comprension_ahora", ""),
            "utilidad": request.form.get("utilidad", ""),
        }
        # RNF-05: se guardan sin referencia al usuario.
        for pregunta, respuesta in preguntas.items():
            if respuesta:
                db.session.add(
                    RespuestaEncuesta(
                        momento="antes" if pregunta == "comprension_antes" else "ahora",
                        pregunta=pregunta,
                        respuesta=respuesta,
                    )
                )
        # Marcamos que ya se ofrecio para no volver a pedirla.
        usuario.encuesta_ofrecida = True
        db.session.commit()
        flash("Gracias por participar en la evaluacion.", "ok")
        return redirect(url_for("perfil.index"))

    return render_template("encuesta.html", usuario=usuario)
