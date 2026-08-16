"""Modelos de autenticacion (RF-16, RF-17, RNF-09)."""

from datetime import datetime, timezone

from src.extensions import db


def _utcnow():
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=_utcnow)


class RevokedToken(db.Model):
    """Lista de revocacion de tokens JWT (RF-17.3: cerrar sesion invalida el token)."""

    __tablename__ = "revoked_tokens"

    jti = db.Column(db.String(64), primary_key=True)
    revoked_at = db.Column(db.DateTime, default=_utcnow)
