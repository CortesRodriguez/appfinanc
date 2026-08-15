"""Blueprint de autenticacion (RF-11, RF-12).

- Registro con Flask-Bcrypt (RF-11.1, RNF-06.1).
- Login/logout con Flask-JWT-Extended en cookie HttpOnly (RF-12.1).
- Consentimiento opcional para la evaluacion (Metodologia).
"""

from __future__ import annotations

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_jwt_extended import (
    create_access_token,
    set_access_cookies,
    unset_jwt_cookies,
)

from .extensions import bcrypt, db
from .models import Usuario

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        consentimiento = bool(request.form.get("consentimiento"))

        errores = []
        if not username or not email or not password:
            errores.append("Debes completar nombre de usuario, correo y contraseña.")
        if len(password) < current_app.config["MIN_PASSWORD_LEN"]:
            errores.append(
                f"La contraseña debe tener al menos {current_app.config['MIN_PASSWORD_LEN']} caracteres."
            )
        if Usuario.query.filter_by(email=email).first():
            errores.append("Ya existe una cuenta registrada con ese correo. Inicia sesion.")

        if errores:
            for e in errores:
                flash(e, "error")
            return render_template(
                "register.html", username=username, email=email, consentimiento=consentimiento
            )

        password_hash = bcrypt.generate_password_hash(password).decode("utf-8")
        usuario = Usuario(
            username=username,
            email=email,
            password_hash=password_hash,
            consentimiento_eval=consentimiento,
        )
        db.session.add(usuario)
        db.session.commit()
        flash("Cuenta creada correctamente. Ya puedes iniciar sesion.", "ok")
        return redirect(url_for("auth.login"))

    return render_template("register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        usuario = Usuario.query.filter_by(email=email).first()
        # Mensaje generico (CU-25 excepcion 1)
        if usuario is None or not bcrypt.check_password_hash(usuario.password_hash, password):
            flash("Credenciales incorrectas. Verifica y reintenta.", "error")
            return render_template("login.html", email=email)

        token = create_access_token(identity=str(usuario.id))
        respuesta = redirect(url_for("main.index"))
        set_access_cookies(respuesta, token)
        return respuesta

    return render_template("login.html")


@bp.route("/logout")
def logout():
    respuesta = redirect(url_for("auth.login"))
    unset_jwt_cookies(respuesta)
    flash("Sesion cerrada.", "ok")
    return respuesta
