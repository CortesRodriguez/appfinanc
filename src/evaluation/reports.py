"""Reportes comparativos y exportacion de resultados (RF-15, CU-09, CU-10)."""

import csv
import io

from .models import SurveyResponse
from .surveys import SURVEY_QUESTIONS


def _scores_by_session(phase: str):
    total_questions = len(SURVEY_QUESTIONS)
    rows = SurveyResponse.query.filter_by(phase=phase).all()

    by_session = {}
    for row in rows:
        by_session.setdefault(row.session_id, []).append(row.correct)

    return {sid: sum(1 for c in correct_list if c) for sid, correct_list in by_session.items() if len(correct_list) == total_questions}


def build_comparative_report():
    """Consolida resultados pre/post por sesion anonima (RF-15.1)."""
    pre_scores = _scores_by_session("pre")
    post_scores = _scores_by_session("post")

    session_ids = sorted(set(pre_scores) & set(post_scores))
    rows = []
    for sid in session_ids:
        pre, post = pre_scores[sid], post_scores[sid]
        rows.append({"session_id": sid, "pre_score": pre, "post_score": post, "delta": post - pre})

    if not rows:
        return {"rows": [], "summary": None}

    avg_pre = sum(r["pre_score"] for r in rows) / len(rows)
    avg_post = sum(r["post_score"] for r in rows) / len(rows)
    avg_delta = sum(r["delta"] for r in rows) / len(rows)

    summary = {
        "participants": len(rows),
        "avg_pre_score": round(avg_pre, 2),
        "avg_post_score": round(avg_post, 2),
        "avg_delta": round(avg_delta, 2),
        "total_questions": len(SURVEY_QUESTIONS),
    }
    return {"rows": rows, "summary": summary}


def export_report_csv() -> str:
    """Genera el contenido CSV del reporte comparativo (RF-15.2, CU-10)."""
    report = build_comparative_report()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["session_id", "pre_score", "post_score", "delta", "total_questions"])
    for row in report["rows"]:
        writer.writerow([row["session_id"], row["pre_score"], row["post_score"], row["delta"], len(SURVEY_QUESTIONS)])

    return buffer.getvalue()
