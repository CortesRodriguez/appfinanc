"""Logica de registro y autenticacion (RF-16, RF-17, RNF-09.1)."""

import re

from src.extensions import bcrypt, db

from .models import User

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AuthError(Exception):
    """Error de negocio de autenticacion, expuesto al Presentador con mensaje comprensible."""


def _derive_username_from_email(email: str) -> str:
    """Genera un `username` unico a partir del prefijo del correo.

    El registro simplificado (RF-16 mejorado) solo pide correo + contrasena,
    por lo que el `username` visible en el perfil se deriva del prefijo del
    email limpiando caracteres no alfanumericos. Si el candidato colisiona
    con otro usuario ya registrado, se agrega un sufijo numerico incremental
    hasta encontrar uno libre.
    """
    prefix = email.split("@", 1)[0]
    base = re.sub(r"[^A-Za-z0-9_]", "", prefix) or "usuario"
    candidate = base
    suffix = 2
    while User.query.filter_by(username=candidate).first():
        candidate = f"{base}_{suffix}"
        suffix += 1
    return candidate


def register_user(
    username: str = None,
    email: str = "",
    password: str = "",
    min_password_length: int = 8,
    acepta_evaluacion: bool | None = None,
) -> User:
    """Registro de usuario (RF-11).

    `acepta_evaluacion` corresponde al casillero opcional de consentimiento
    para participar en la Metodología de Evaluación del proyecto (encuesta
    retrospectiva post-uso). Puede ser True, False o None si el usuario no
    marcó nada en el formulario. La encuesta solo se ofrece a quienes lo
    marcaron explícitamente en True.
    """
    email = (email or "").strip().lower()

    if not EMAIL_RE.match(email):
        raise AuthError("El correo electrónico no tiene un formato válido.")
    if len(password or "") < min_password_length:
        raise AuthError(f"La contraseña debe tener al menos {min_password_length} caracteres.")

    # RF-16.2: el correo no debe estar previamente registrado
    if User.query.filter_by(email=email).first():
        raise AuthError("Ese correo electrónico ya está registrado.")

    username = (username or "").strip() or _derive_username_from_email(email)

    # RF-16.3: encriptar la contrasena mediante Flask-Bcrypt antes de almacenarla
    password_hash = bcrypt.generate_password_hash(password).decode("utf-8")
    user = User(
        username=username,
        email=email,
        password_hash=password_hash,
        acepta_evaluacion=acepta_evaluacion,
    )
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
