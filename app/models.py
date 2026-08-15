"""Modelos ORM (Fig. 2.1 del anteproyecto).

Cinco entidades:
- Usuario           (cuenta y consentimiento de evaluacion)
- Consulta          (cada interaccion del usuario con un indicador)
- Regeneracion     (cada solicitud de nueva explicacion)
- ExplicacionCache (RF-14.5: reutilizacion de la ultima explicacion)
- RespuestaEncuesta (anonimizada, sin vinculo con la cuenta)
"""

from __future__ import annotations

from datetime import datetime, timezone

from .extensions import db


class Usuario(db.Model):
    __tablename__ = "usuario"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    consentimiento_eval = db.Column(db.Boolean, default=False, nullable=False)
    encuesta_ofrecida = db.Column(db.Boolean, default=False, nullable=False)
    creado_en = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    consultas = db.relationship("Consulta", backref="usuario", lazy=True)
    explicaciones = db.relationship("ExplicacionCache", backref="usuario", lazy=True)


class Consulta(db.Model):
    __tablename__ = "consulta"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    ticker = db.Column(db.String(30), nullable=False)
    indicador = db.Column(db.String(30), nullable=False)
    rango = db.Column(db.String(20), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    riesgo = db.Column(db.String(10), nullable=False)
    fecha_hora = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    regeneraciones = db.relationship("Regeneracion", backref="consulta", lazy=True)


class Regeneracion(db.Model):
    __tablename__ = "regeneracion"

    id = db.Column(db.Integer, primary_key=True)
    consulta_id = db.Column(db.Integer, db.ForeignKey("consulta.id"), nullable=False)
    fecha_hora = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class ExplicacionCache(db.Model):
    __tablename__ = "explicacion_cache"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    ticker = db.Column(db.String(30), nullable=False)
    indicador = db.Column(db.String(30), nullable=False)
    texto = db.Column(db.Text, nullable=False)
    valor = db.Column(db.Float, nullable=False)
    riesgo = db.Column(db.String(10), nullable=False)
    generada_en = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint("usuario_id", "ticker", "indicador", name="uq_cache_por_usuario"),
    )


class RespuestaEncuesta(db.Model):
    """RNF-05: respuestas anonimizadas, sin FK a Usuario."""

    __tablename__ = "respuesta_encuesta"

    id = db.Column(db.Integer, primary_key=True)
    momento = db.Column(db.String(10), nullable=False)  # "antes" | "ahora"
    pregunta = db.Column(db.String(200), nullable=False)
    respuesta = db.Column(db.String(200), nullable=False)
    fecha_hora = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
