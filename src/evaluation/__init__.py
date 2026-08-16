"""Modulo de Evaluacion y Validacion (RF-11 a RF-15)."""

from sqlalchemy.exc import IntegrityError

from src.extensions import db

from .models import EvaluationSession


def ensure_evaluation_session(session_id: str):
    """Crea la fila de `EvaluationSession` si todavia no existe.

    El dashboard dispara varias solicitudes en paralelo (una por
    indicador) la primera vez que un usuario interactua en una sesion
    nueva. Si todas verifican "no existe" antes de que cualquiera
    alcance a insertar, mas de una intenta crear la misma fila al mismo
    tiempo y la segunda choca con la restriccion UNIQUE de la clave
    primaria. Se captura ese conflicto puntual: significa que otra
    solicitud concurrente ya la creo, que es exactamente el resultado
    que se buscaba.
    """
    if db.session.get(EvaluationSession, session_id):
        return

    try:
        db.session.add(EvaluationSession(session_id=session_id))
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
