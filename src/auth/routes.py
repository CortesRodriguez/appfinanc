"""Rutas de autenticacion: registro, login, logout (RF-16, RF-17, CU-11, CU-12)."""

from flask import Blueprint, current_app, jsonify, render_template, request
from flask_jwt_extended import (
    create_access_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
    set_access_cookies,
    unset_jwt_cookies,
    verify_jwt_in_request,
)

from src.extensions import db

from .models import RevokedToken, User
from .service import AuthError, authenticate_user, register_user

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

    try:
        user = register_user(
            payload.get("username", ""),
            payload.get("email", ""),
            payload.get("password", ""),
            min_password_length=current_app.config["PASSWORD_MIN_LENGTH"],
        )
    except AuthError as exc:
        return jsonify({"error": str(exc)}), 409

    # CU-11: el registro deja al usuario autenticado, sin pedirle iniciar sesion aparte
    token = create_access_token(identity=str(user.id))
    response = jsonify({"username": user.username, "email": user.email})
    set_access_cookies(response, token)
    return response, 201


@bp.route("/api/auth/login", methods=["POST"])
def api_login():
    payload = request.get_json(silent=True) or {}

    try:
        user = authenticate_user(payload.get("email", ""), payload.get("password", ""))
    except AuthError as exc:
        return jsonify({"error": str(exc)}), 401

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
