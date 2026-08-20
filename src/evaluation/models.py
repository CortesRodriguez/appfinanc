"""Modelos de persistencia del Módulo de Evaluación.

La `EvaluationSession`, `QueryLog`, `InstrumentVisit` y `CoherenceCheck`
son datos operativos del sistema y siguen ligados al `session_id`
anónimo de Flask (RNF-05.1, RNF-05.2).

`SurveyResponse` es distinto: pertenece al plano de instrumentación de
investigación (Instrumento 1 — Autoevaluación Retrospectiva). Por
diseño **no** se vincula con `session_id` ni con `user_id`: cada
respuesta se identifica únicamente con un `response_token` generado en
el momento del envío. Esto garantiza que las respuestas sean anónimas
por construcción (no por disciplina): un JOIN entre `users` y
`survey_responses` es imposible porque no existe una columna
compartida.
"""

import uuid
from datetime import datetime, timezone

from src.extensions import db


def _utcnow():
    return datetime.now(timezone.utc)


def _new_response_token():
    return str(uuid.uuid4())


class EvaluationSession(db.Model):
    __tablename__ = "evaluation_sessions"

    session_id = db.Column(db.String(36), primary_key=True)
    created_at = db.Column(db.DateTime, default=_utcnow)
    interaction_seconds = db.Column(db.Float, default=0.0)  # RF-14.1


class SurveyResponse(db.Model):
    """Una fila por (respuesta completa, concepto) de la autoevaluación retrospectiva.

    Instrumento 1: la persona, al enviar la encuesta, produce un
    `response_token` único; por cada concepto evaluado se guarda una
    fila con `scale_before` (1-5) y `scale_now` (1-5). El delta subjetivo
    de comprensión por concepto es `scale_now - scale_before`.

    Deliberadamente no lleva `user_id` ni `session_id` para preservar
    el anonimato de la respuesta frente a cualquier consulta posterior.
    """

    __tablename__ = "survey_responses"

    id = db.Column(db.Integer, primary_key=True)
    response_token = db.Column(db.String(36), nullable=False, index=True)
    concept_id = db.Column(db.String(32), nullable=False)
    scale_before = db.Column(db.Integer, nullable=False)  # 1..5, auto-percepción antes
    scale_now = db.Column(db.Integer, nullable=False)  # 1..5, auto-percepción ahora
    created_at = db.Column(db.DateTime, default=_utcnow)


class QueryLog(db.Model):
    __tablename__ = "query_logs"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(36), db.ForeignKey("evaluation_sessions.session_id"), nullable=False)
    instrument = db.Column(db.String(20), nullable=False)
    indicator = db.Column(db.String(20), nullable=False)
    source = db.Column(db.String(30), nullable=False)
    processing_time_ms = db.Column(db.Integer, nullable=False)  # RNF-01.2
    created_at = db.Column(db.DateTime, default=_utcnow)

    # RF-18.1: perfil de aprendizaje (indicadores consultados y explicaciones regeneradas)
    # user_id queda en null para consultas anonimas (sin cuenta iniciada), que siguen
    # funcionando exactamente igual que antes de agregar autenticacion.
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    is_regeneration = db.Column(db.Boolean, default=False)
    explanation_text = db.Column(db.Text, nullable=True)
    variant = db.Column(db.Integer, default=0)


class InstrumentVisit(db.Model):
    """Una fila por instrumento seleccionado en el dashboard (RF-19.2, RF-19.3).

    Separada de `QueryLog` a proposito: seleccionar un instrumento dispara
    cuatro consultas en paralelo (una por indicador) que quedan cada una
    en `QueryLog` para el detalle tecnico (RNF-01.2, RF-13), pero para el
    usuario esas cuatro consultas son "una sola accion" (ver un
    instrumento). Contarlas de a cuatro en el perfil de aprendizaje
    infla el numero de forma que no coincide con lo que el usuario hizo.
    """

    __tablename__ = "instrument_visits"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    instrument = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=_utcnow)


class CoherenceCheck(db.Model):
    __tablename__ = "coherence_checks"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(36), nullable=False)
    instrument = db.Column(db.String(20), nullable=False)
    indicator = db.Column(db.String(20), nullable=False)
    value = db.Column(db.Float, nullable=False)
    risk_level = db.Column(db.String(10), nullable=False)
    explanation_text = db.Column(db.Text, nullable=False)
    coherent = db.Column(db.Boolean, nullable=False)
    reason = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default="pendiente")  # pendiente | revisado
    created_at = db.Column(db.DateTime, default=_utcnow)
