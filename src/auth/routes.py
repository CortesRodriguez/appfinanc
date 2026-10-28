"""Rutas de autenticacion: registro, login, logout (RF-16, RF-17, CU-11, CU-12)."""

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, url_for
from flask_jwt_extended import (
    create_access_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
    set_access_cookies,
    unset_jwt_cookies,
    verify_jwt_in_request,
)

from src.extensions import db, oauth

from .models import RevokedToken, User
from .service import AuthError, authenticate_user, login_or_register_google_user, register_user

bp = Blueprint("auth", __name__)


@bp.route("/registro")
def register_page():
    return render_template("register.html")


@bp.route("/login")
def login_page():
    return render_template("login.html")


@bp.route("/api/auth/registro", methods=["POST"])
def api_register():
    payload = request.get_json(silent=True) or {}

    # RF-11.1: nombre de usuario, correo y contrasena (con confirmacion) son obligatorios.
    password = payload.get("password", "")
    if payload.get("password_confirm") != password:
        return jsonify({"error": "Las contraseñas no coinciden."}), 400

    try:
        user = register_user(
            username=payload.get("username", ""),
            email=payload.get("email", ""),
            password=password,
            min_password_length=current_app.config["PASSWORD_MIN_LENGTH"],
            max_password_length=current_app.config["PASSWORD_MAX_LENGTH"],
            experience_level=payload.get("experience_level"),
        )
    except AuthError as exc:
        return jsonify({"error": str(exc)}), exc.status

    # CU-24: el registro deja al usuario autenticado, sin pedirle iniciar sesion aparte
    token = create_access_token(identity=str(user.id))
    response = jsonify({"username": user.username, "email": user.email})
    set_access_cookies(response, token)
    return response, 201


@bp.route("/auth/google/login")
def google_login():
    if not current_app.config.get("GOOGLE_CLIENT_ID"):
        return jsonify({"error": "Login con Google no está configurado."}), 404
    return oauth.google.authorize_redirect(url_for("auth.google_callback", _external=True))


@bp.route("/auth/google/callback")
def google_callback():
    token = oauth.google.authorize_access_token()
    userinfo = token["userinfo"]

    try:
        user = login_or_register_google_user(
            google_id=userinfo["sub"], email=userinfo.get("email", ""), name=userinfo.get("name", "")
        )
    except AuthError as exc:
        return redirect(url_for("auth.login_page", oauth_error=str(exc)))

    jwt_token = create_access_token(identity=str(user.id))
    response = redirect(url_for("web.index"))
    set_access_cookies(response, jwt_token)
    return response


@bp.route("/api/auth/login", methods=["POST"])
def api_login():
    payload = request.get_json(silent=True) or {}

    try:
        user = authenticate_user(
            payload.get("email", ""),
            payload.get("password", ""),
            max_attempts=current_app.config["LOGIN_MAX_ATTEMPTS"],
            lock_minutes=current_app.config["LOGIN_LOCK_MINUTES"],
        )
    except AuthError as exc:
        return jsonify({"error": str(exc)}), exc.status

    token = create_access_token(identity=str(user.id))
    response = jsonify({"username": user.username, "email": user.email})
    set_access_cookies(response, token)
    return response


@bp.route("/api/auth/logout", methods=["POST"])
@jwt_required()
def api_logout():
    # RF-17.3: cerrar sesion invalida el token asociado
    jti = get_jwt()["jti"]
    db.session.add(RevokedToken(jti=jti))
    db.session.commit()

    response = jsonify({"ok": True})
    unset_jwt_cookies(response)
    return response


@bp.route("/api/auth/me")
def api_me():
    """Info minima de sesion para que el frontend sepa si hay un usuario autenticado."""
    try:
        verify_jwt_in_request(optional=True)
    except Exception:  # noqa: BLE001 - token invalido/expirado: se trata como anonimo
        return jsonify({"authenticated": False})

    user_id = get_jwt_identity()
    if not user_id:
        return jsonify({"authenticated": False})

    user = db.session.get(User, int(user_id))
    if not user:
        return jsonify({"authenticated": False})

    return jsonify({"authenticated": True, "username": user.username, "email": user.email})
