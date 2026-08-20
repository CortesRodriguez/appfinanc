"""Tests del Instrumento 1 — Autoevaluación Retrospectiva."""

import pytest

from src.evaluation import surveys
from src.evaluation.models import SurveyResponse
from src.evaluation.reports import build_comparative_report, export_report_csv


def _valid_answers(before=1, now=5):
    return {c["id"]: {"before": before, "now": now} for c in surveys.SURVEY_CONCEPTS}


def test_submit_rejects_incomplete_answers(app):
    with app.app_context():
        first_concept = surveys.SURVEY_CONCEPTS[0]["id"]
        result = surveys.submit_survey({first_concept: {"before": 3, "now": 4}})
        assert "missing" in result
        # Faltan todos menos el que envié
        assert len(result["missing"]) == len(surveys.SURVEY_CONCEPTS) - 1


def test_submit_rejects_scale_out_of_range(app):
    with app.app_context():
        answers = _valid_answers()
        answers[surveys.SURVEY_CONCEPTS[0]["id"]] = {"before": 0, "now": 5}
        with pytest.raises(surveys.SurveyValidationError):
            surveys.submit_survey(answers)


def test_submit_rejects_unknown_concept(app):
    with app.app_context():
        answers = _valid_answers()
        answers["concepto_inexistente"] = {"before": 1, "now": 5}
        with pytest.raises(surveys.SurveyValidationError):
            surveys.submit_survey(answers)


def test_submit_persists_anonymously(app):
    with app.app_context():
        answers = _valid_answers(before=2, now=4)
        result = surveys.submit_survey(answers)

        assert result["total_concepts"] == len(surveys.SURVEY_CONCEPTS)
        assert result["avg_delta"] == 2.0
        assert "response_token" in result

        # Cada fila persiste el token, sin user_id ni session_id.
        rows = SurveyResponse.query.all()
        assert len(rows) == len(surveys.SURVEY_CONCEPTS)
        for row in rows:
            assert row.response_token == result["response_token"]
            # La frontera de anonimato: el modelo no expone user_id ni session_id.
            assert not hasattr(row, "user_id")
            assert not hasattr(row, "session_id")


def test_submit_generates_fresh_token_each_time(app):
    with app.app_context():
        first = surveys.submit_survey(_valid_answers(before=1, now=3))
        second = surveys.submit_survey(_valid_answers(before=2, now=5))
        assert first["response_token"] != second["response_token"]


def test_comparative_report_aggregates_by_response(app):
    with app.app_context():
        surveys.submit_survey(_valid_answers(before=1, now=5))
        surveys.submit_survey(_valid_answers(before=3, now=4))

        report = build_comparative_report()
        assert report["summary"]["participants"] == 2
        # Δ subjetivo promedio: ((5-1) + (4-3)) / 2 = 2.5
        assert report["summary"]["avg_delta"] == 2.5

        # Cada respuesta aparece con su token, no con user_id.
        for row in report["rows"]:
            assert "response_token" in row
            assert "user_id" not in row


def test_csv_export_uses_response_token(app):
    with app.app_context():
        surveys.submit_survey(_valid_answers(before=2, now=5))
        csv_content = export_report_csv()
        assert "response_token" in csv_content
        assert "session_id" not in csv_content
        assert "phase" not in csv_content
