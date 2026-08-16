"""Modelos de persistencia del Modulo de Evaluacion.

Todos los registros se asocian a un `session_id` anonimo generado por
Flask (UUID de sesion), nunca a datos personales identificables
(RNF-05.1, RNF-05.2).
"""

from datetime import datetime, timezone

from src.extensions import db


def _utcnow():
    return datetime.now(timezone.utc)


class EvaluationSession(db.Model):
    __tablename__ = "evaluation_sessions"

    session_id = db.Column(db.String(36), primary_key=True)
    created_at = db.Column(db.DateTime, default=_utcnow)
    interaction_seconds = db.Column(db.Float, default=0.0)  # RF-14.1


class SurveyResponse(db.Model):
    __tablename__ = "survey_responses"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(36), db.ForeignKey("evaluation_sessions.session_id"), nullable=False)
    phase = db.Column(db.String(4), nullable=False)  # 'pre' o 'post' (RF-11.1 / RF-11.2)
    question_id = db.Column(db.String(16), nullable=False)
    answer_index = db.Column(db.Integer, nullable=False)
    correct = db.Column(db.Boolean, nullable=False)
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
