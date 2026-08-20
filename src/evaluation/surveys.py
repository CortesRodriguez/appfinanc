"""Instrumento 1 — Autoevaluación Retrospectiva (RF-11, RF-12, CU-06, CU-07).

Diseño retrospectivo, no pre/post: una sola encuesta post-uso donde la
persona reporta, para cada concepto financiero evaluado, en escala de
1 a 5 qué tan bien lo entendía ANTES de usar la herramienta y qué tan
bien lo entiende AHORA. El delta subjetivo por concepto es
`scale_now - scale_before`.

Trade-off explícito: se sacrifica precisión ("antes" depende de la
memoria) a cambio de no perder participantes por abandono entre dos
sesiones separadas. Es una técnica reconocida de evaluación de
programas.

Anonimato: al enviar la respuesta se genera un `response_token` nuevo
(UUID) que **no** se vincula al `user_id` ni al `session_id` de Flask.
Un JOIN entre una respuesta y una cuenta es imposible por construcción.
"""

import json
import os
import uuid

from src.constants import SURVEY_SCALE_MAX, SURVEY_SCALE_MIN
from src.extensions import db

from .models import SurveyResponse

_DATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "survey_concepts.json",
)

with open(_DATA_PATH, encoding="utf-8") as f:
    SURVEY_CONCEPTS = json.load(f)

_CONCEPT_IDS = {c["id"] for c in SURVEY_CONCEPTS}


def get_concepts():
    """Lista de conceptos a autoevaluar (id, label, description)."""
    return [dict(c) for c in SURVEY_CONCEPTS]


class SurveyValidationError(ValueError):
    """La respuesta enviada no es válida (faltan conceptos o escalas fuera de rango)."""


def _validate_answers(answers: dict):
    """Verifica que `answers` tenga una entrada por concepto con escalas 1..5.

    Formato esperado:
        {concept_id: {"before": int, "now": int}, ...}
    """
    if not isinstance(answers, dict):
        raise SurveyValidationError("El cuerpo de la encuesta debe ser un objeto.")

    missing = [c["id"] for c in SURVEY_CONCEPTS if c["id"] not in answers]
    if missing:
        return missing

    for concept_id, pair in answers.items():
        if concept_id not in _CONCEPT_IDS:
            raise SurveyValidationError(f"Concepto desconocido: {concept_id}")
        if not isinstance(pair, dict) or "before" not in pair or "now" not in pair:
            raise SurveyValidationError(
                f"Cada respuesta debe incluir 'before' y 'now' (concepto {concept_id})."
            )
        for scale_key in ("before", "now"):
            value = pair[scale_key]
            if not isinstance(value, int) or not (SURVEY_SCALE_MIN <= value <= SURVEY_SCALE_MAX):
                raise SurveyValidationError(
                    f"La escala '{scale_key}' del concepto {concept_id} debe ser entera entre "
                    f"{SURVEY_SCALE_MIN} y {SURVEY_SCALE_MAX}."
                )
    return []


def submit_survey(answers: dict):
    """Guarda una respuesta retrospectiva anonimizada.

    Genera un `response_token` nuevo (UUID) que identifica esta respuesta y
    solo esta respuesta. No recibe `user_id` ni `session_id`: la frontera
    de anonimato se garantiza en la firma de la función, no por disciplina
    del caller.

    Retorna un dict con:
      - `response_token`: string
      - `total_concepts`: int
      - `deltas`: [{concept_id, before, now, delta}, ...]
      - `avg_before`, `avg_now`, `avg_delta`: promedios de auto-percepción

    Si faltan conceptos por responder, retorna `{"missing": [...]}` sin
    guardar nada (Excepción 1, CU-06).
    """
    missing = _validate_answers(answers)
    if missing:
        return {"missing": missing}

    response_token = str(uuid.uuid4())
    deltas = []
    for concept in SURVEY_CONCEPTS:
        cid = concept["id"]
        before = int(answers[cid]["before"])
        now = int(answers[cid]["now"])
        db.session.add(
            SurveyResponse(
                response_token=response_token,
                concept_id=cid,
                scale_before=before,
                scale_now=now,
            )
        )
        deltas.append({"concept_id": cid, "before": before, "now": now, "delta": now - before})

    db.session.commit()

    total = len(deltas)
    avg_before = sum(d["before"] for d in deltas) / total
    avg_now = sum(d["now"] for d in deltas) / total
    avg_delta = sum(d["delta"] for d in deltas) / total
    return {
        "response_token": response_token,
        "total_concepts": total,
        "deltas": deltas,
        "avg_before": round(avg_before, 2),
        "avg_now": round(avg_now, 2),
        "avg_delta": round(avg_delta, 2),
    }
