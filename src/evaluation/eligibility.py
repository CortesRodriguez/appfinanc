"""Elegibilidad para el Instrumento 1 (Autoevaluación Retrospectiva).

Responde una única pregunta: ¿esta cuenta cumple los criterios para
que se le ofrezca la encuesta retrospectiva? La respuesta depende
únicamente del historial de visitas a instrumentos: si la persona ha
alcanzado el umbral `SURVEY_THRESHOLD`, es elegible.

La invitación a la encuesta se ofrece solo a usuarios registrados;
los anónimos no son elegibles por diseño (no pueden dar consentimiento
formal). Ver `docs/diagramas/componentes/componentes.md`.
"""

from src.constants import SURVEY_THRESHOLD
from src.evaluation.models import InstrumentVisit


def instrument_visit_count(user_id: int) -> int:
    """Cuenta cuántas veces la persona ha seleccionado un instrumento.

    Se usa `InstrumentVisit`, no `QueryLog`: seleccionar un instrumento
    dispara cuatro consultas (una por indicador) que inflarían el
    conteo si contáramos `QueryLog`. Ver `models.InstrumentVisit`.
    """
    if user_id is None:
        return 0
    return InstrumentVisit.query.filter_by(user_id=user_id).count()


def is_eligible_for_survey(user_id) -> bool:
    """`True` si la cuenta ha alcanzado el umbral de consultas.

    - `user_id` es `None` (usuario anónimo) → siempre `False`.
    - No verifica consentimiento: eso es responsabilidad del coordinador
      que consume esta función. Aquí solo se responde por elegibilidad
      por exposición al sistema.
    """
    if user_id is None:
        return False
    return instrument_visit_count(int(user_id)) >= SURVEY_THRESHOLD
