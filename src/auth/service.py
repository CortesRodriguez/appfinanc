"""Logica de registro y autenticacion (RF-16, RF-17, RNF-09.1)."""

import re

from src.extensions import bcrypt, db

from .models import User

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AuthError(Exception):
    """Error de negocio de autenticacion, expuesto al Presentador con mensaje comprensible."""


def register_user(username: str, email: str, password: str, min_password_length: int = 8) -> User:
    username = (username or "").strip()
    email = (email or "").strip().lower()

    if not username:
        raise AuthError("Debes indicar un nombre de usuario.")
    if not EMAIL_RE.match(email):
        raise AuthError("El correo electrónico no tiene un formato válido.")
    if len(password or "") < min_password_length:
        raise AuthError(f"La contraseña debe tener al menos {min_password_length} caracteres.")

    # RF-16.2: el correo no debe estar previamente registrado
    if User.query.filter_by(email=email).first():
        raise AuthError("Ese correo electrónico ya está registrado.")

    # RF-16.3: encriptar la contrasena mediante Flask-Bcrypt antes de almacenarla
    password_hash = bcrypt.generate_password_hash(password).decode("utf-8")
    user = User(username=username, email=email, password_hash=password_hash)
    db.session.add(user)
    db.session.commit()
    return user


def authenticate_user(email: str, password: str) -> User:
    email = (email or "").strip().lower()
    user = User.query.filter_by(email=email).first()

    # Mensaje generico deliberado: no revela si el correo existe (Excepcion 1, CU-12)
    if not user or not bcrypt.check_password_hash(user.password_hash, password or ""):
        raise AuthError("Correo electrónico o contraseña incorrectos.")

    return user
