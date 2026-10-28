"""Modelos de persistencia: QueryLog e InstrumentVisit.

`QueryLog` registra cada consulta de indicador (historial del perfil, RF-10).
`InstrumentVisit` registra cada selección de instrumento (para perfil
adaptativo, RF-13/RF-14).
"""

from datetime import datetime, timezone

from src.extensions import db


def _utcnow():
    return datetime.now(timezone.utc)


class QueryLog(db.Model):
    __tablename__ = "query_logs"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(36), nullable=False)
    instrument = db.Column(db.String(20), nullable=False)
    indicator = db.Column(db.String(20), nullable=False)
    source = db.Column(db.String(30), nullable=False)
    processing_time_ms = db.Column(db.Integer, nullable=False)  # RNF-01.2
    created_at = db.Column(db.DateTime(timezone=True), default=_utcnow)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    is_regeneration = db.Column(db.Boolean, default=False)
    explanation_text = db.Column(db.Text, nullable=True)
    variant = db.Column(db.Integer, default=0)

    # Detalle de lo que vio el usuario, para el historial de /perfil (RF-10, CU-30).
    # Nullable: las filas anteriores a la migracion 0004 no lo tienen.
    value = db.Column(db.Float, nullable=True)
    unit = db.Column(db.String(10), nullable=True)
    risk_level = db.Column(db.String(10), nullable=True)
    period_days = db.Column(db.Integer, nullable=True)


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
    created_at = db.Column(db.DateTime(timezone=True), default=_utcnow)


