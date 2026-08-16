"""Encuestas de comprension pre/post-test (RF-11, RF-12, CU-06, CU-07)."""

import json
import os

from src.extensions import db
from .models import EvaluationSession, SurveyResponse

_DATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "survey_questions.json"
)

with open(_DATA_PATH, encoding="utf-8") as f:
    SURVEY_QUESTIONS = json.load(f)

_QUESTIONS_BY_ID = {q["id"]: q for q in SURVEY_QUESTIONS}


def get_questions():
    # No se expone `correct_index` al cliente
    return [{"id": q["id"], "question": q["question"], "options": q["options"]} for q in SURVEY_QUESTIONS]


def has_completed_phase(session_id: str, phase: str) -> bool:
    return (
        SurveyResponse.query.filter_by(session_id=session_id, phase=phase).count() > 0
    )


def submit_survey(session_id: str, phase: str, answers: dict):
    """Guarda las respuestas de una fase (pre o post) de forma anonimizada.

    `answers` es {question_id: answer_index}. Retorna (score, total,
    missing_question_ids). Si faltan preguntas por responder, no se
    guarda nada y se retornan los ids faltantes (Excepcion 1, CU-06).
    """
    missing = [q["id"] for q in SURVEY_QUESTIONS if q["id"] not in answers]
    if missing:
        return None, len(SURVEY_QUESTIONS), missing

    if not db.session.get(EvaluationSession, session_id):
        db.session.add(EvaluationSession(session_id=session_id))

    score = 0
    for question in SURVEY_QUESTIONS:
        qid = question["id"]
        answer_index = int(answers[qid])
        correct = answer_index == question["correct_index"]
        score += int(correct)
        db.session.add(
            SurveyResponse(
                session_id=session_id,
                phase=phase,
                question_id=qid,
                answer_index=answer_index,
                correct=correct,
            )
        )

    db.session.commit()
    return score, len(SURVEY_QUESTIONS), []


def get_score(session_id: str, phase: str):
    responses = SurveyResponse.query.filter_by(session_id=session_id, phase=phase).all()
    if not responses:
        return None
    correct = sum(1 for r in responses if r.correct)
    return {"correct": correct, "total": len(responses)}
