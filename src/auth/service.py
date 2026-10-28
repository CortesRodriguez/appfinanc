"""Logica de registro y autenticacion (RF-16, RF-17, RNF-09.1)."""

import re
from datetime import datetime, timedelta, timezone

from src.extensions import bcrypt, db

from .models import User

EMAIL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._%+-]*@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$")
PASSWORD_LETTER_RE = re.compile(r"[A-Za-z]")
PASSWORD_DIGIT_RE = re.compile(r"\d")
PASSWORD_SPECIAL_RE = re.compile(r"[!@#$%^&*()_+\-=,.?\":{}|<>]")

# bcrypt solo procesa los primeros 72 bytes y bcrypt 5.x lanza ValueError si se
# le pasa mas: 64 caracteres con tildes o emojis pueden superar ese limite.
BCRYPT_MAX_BYTES = 72
USERNAME_MAX_LENGTH = 80  # = users.username VARCHAR(80)

# Experiencia declarada al registrarse (RF-13.2): fija el nivel de detalle inicial.
EXPERIENCE_LEVELS = ("nunca", "poco", "experiencia")


def normalize_experience(value) -> str | None:
    """Devuelve un valor valido de EXPERIENCE_LEVELS, None si no se declaro, o AuthError (400)."""
    if value is None or value == "":
        return None
    if not isinstance(value, str) or value.strip().lower() not in EXPERIENCE_LEVELS:
        raise AuthError("El nivel de experiencia indicado no es válido.")
    return value.strip().lower()


class AuthError(Exception):
    """Error de negocio de autenticacion, expuesto al Presentador con mensaje comprensible.

    `status` es el codigo HTTP que corresponde: 400 validacion, 401 credenciales,
    409 conflicto (correo/usuario ya existe), 429 cuenta bloqueada temporalmente.
    """

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def register_user(
    username: str = None,
    email: str = "",
    password: str = "",
    min_password_length: int = 8,
    max_password_length: int = 64,
    experience_level: str = None,
) -> User:
    """Registro de usuario (RF-11, CU-24)."""
    email = (email or "").strip().lower()
    username = (username or "").strip()
    password = password or ""
    experience_level = normalize_experience(experience_level)

    if not username:
        raise AuthError("El nombre de usuario es obligatorio.")
    if len(username) > USERNAME_MAX_LENGTH:
        raise AuthError(f"El nombre de usuario no puede superar los {USERNAME_MAX_LENGTH} caracteres.")
    if not EMAIL_RE.match(email):
        raise AuthError("El correo electrónico no tiene un formato válido (ejemplo: nombre@dominio.cl).")
    if len(password) < min_password_length:
        raise AuthError(f"La contraseña debe tener al menos {min_password_length} caracteres.")
    if len(password) > max_password_length:
        raise AuthError(f"La contraseña no puede superar los {max_password_length} caracteres.")
    if len(password.encode("utf-8")) > BCRYPT_MAX_BYTES:
        raise AuthError(
            f"La contraseña es demasiado larga: ocupa más de {BCRYPT_MAX_BYTES} bytes "
            "(los caracteres con tilde o símbolos ocupan más de uno). Usa una más corta."
        )
    if not PASSWORD_LETTER_RE.search(password):
        raise AuthError("La contraseña debe incluir al menos una letra.")
    if not PASSWORD_DIGIT_RE.search(password):
        raise AuthError("La contraseña debe incluir al menos un número.")
    if not PASSWORD_SPECIAL_RE.search(password):
        raise AuthError(
            'La contraseña debe incluir al menos un carácter especial (ej: !, @, #, $). '
            "Ejemplo válido: Clave123!"
        )

    # RF-16.2 / CU-24 Excepcion 1: el correo no debe estar previamente registrado
    if User.query.filter_by(email=email).first():
        raise AuthError("Ese correo electrónico ya está registrado. Inicia sesión en su lugar.", status=409)

    if User.query.filter_by(username=username).first():
        raise AuthError("Ese nombre de usuario ya está en uso.", status=409)

    # RF-16.3: encriptar la contrasena mediante Flask-Bcrypt antes de almacenarla
    password_hash = bcrypt.generate_password_hash(password).decode("utf-8")
    user = User(
        username=username,
        email=email,
        password_hash=password_hash,
        experience_level=experience_level,
    )
    db.session.add(user)
    db.session.commit()
    return user


def authenticate_user(email: str, password: str, max_attempts: int = 5, lock_minutes: int = 15) -> User:
    """Valida credenciales con bloqueo temporal anti fuerza bruta (CU-25).

    Tras `max_attempts` fallos seguidos para un correo, la cuenta rechaza todo
    intento (incluso con la clave correcta) durante `lock_minutes`. Un login
    exitoso reinicia el contador. Con un correo inexistente no hay fila donde
    contar: se responde con el mismo mensaje generico.
    """
    email = (email or "").strip().lower()
    user = User.query.filter_by(email=email).first()

    now = datetime.now(timezone.utc)
    locked_until = user.locked_until if user else None
    # Defensivo: si el driver devolviera un datetime naive, se asume UTC.
    if locked_until and locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    if locked_until and locked_until > now:
        remaining = max(1, int((locked_until - now).total_seconds() // 60) + 1)
        raise AuthError(
            f"Demasiados intentos fallidos. Intenta de nuevo en {remaining} minuto(s).", status=429
        )

    # Mensaje generico deliberado: no revela si el correo existe (Excepcion 1, CU-25)
    if not user or not user.password_hash or not bcrypt.check_password_hash(user.password_hash, password or ""):
        if user:
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
            if user.failed_login_attempts >= max_attempts:
                user.locked_until = now + timedelta(minutes=lock_minutes)
                user.failed_login_attempts = 0
            db.session.commit()
        raise AuthError("Correo electrónico o contraseña incorrectos.", status=401)

    if user.failed_login_attempts or user.locked_until:
        user.failed_login_attempts = 0
        user.locked_until = None
        db.session.commit()
    return user


def _unique_username_from(seed: str) -> str:
    base = (seed or "").strip() or "usuario"
    base = base.split("@")[0] or "usuario"
    if not User.query.filter_by(username=base).first():
        return base

    suffix = 2
    while User.query.filter_by(username=f"{base}{suffix}").first():
        suffix += 1
    return f"{base}{suffix}"


def login_or_register_google_user(google_id: str, email: str, name: str = "") -> User:
    """Login o registro vía Google OAuth. Las cuentas por contraseña no se vinculan
    automáticamente a una cuenta de Google con el mismo correo (riesgo de seguridad)."""
    email = (email or "").strip().lower()

    user = User.query.filter_by(google_id=google_id).first()
    if user:
        return user

    user = User.query.filter_by(email=email).first()
    if user:
        raise AuthError("Ese correo ya está registrado con contraseña. Inicia sesión con tu contraseña.", status=409)

    user = User(
        username=_unique_username_from(name or email),
        email=email,
        password_hash=None,
        google_id=google_id,
    )
    db.session.add(user)
    db.session.commit()
    return user
