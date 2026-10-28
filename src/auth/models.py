"""Modelos de autenticacion (RF-16, RF-17, RNF-09)."""

from datetime import datetime, timezone

from src.extensions import db


def _utcnow():
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False, unique=True, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=True)
    google_id = db.Column(db.String(255), unique=True, nullable=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=_utcnow)

    # Experiencia declarada ("nunca" | "poco" | "experiencia"): punto de partida
    # del nivel de detalle de las explicaciones (RF-13.2). NULL = no declarada.
    experience_level = db.Column(db.String(20), nullable=True)
    # Momento del ultimo cambio de experiencia: solo las regeneraciones ("No entendi esto")
    # posteriores cuentan para bajar el nivel de cada indicador. NULL = cuentan todas.
    level_reset_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Bloqueo anti fuerza bruta (ver authenticate_user)
    failed_login_attempts = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    locked_until = db.Column(db.DateTime(timezone=True), nullable=True)


class RevokedToken(db.Model):
    """Lista de revocacion de tokens JWT (RF-17.3: cerrar sesion invalida el token)."""

    __tablename__ = "revoked_tokens"

    jti = db.Column(db.String(64), primary_key=True)
    revoked_at = db.Column(db.DateTime(timezone=True), default=_utcnow)
