from src.evaluation import surveys
from src.evaluation.reports import build_comparative_report


def test_submit_survey_rejects_incomplete_answers(app):
    with app.app_context():
        score, total, missing = surveys.submit_survey("session-1", "pre", {"q1": 0})
        assert score is None
        assert missing  # deben faltar preguntas


def test_submit_and_score_survey(app):
    with app.app_context():
        answers = {q["id"]: q["correct_index"] for q in surveys.SURVEY_QUESTIONS}
        score, total, missing = surveys.submit_survey("session-2", "pre", answers)
        assert missing == []
        assert score == total

        result = surveys.get_score("session-2", "pre")
        assert result["correct"] == total


def test_comparative_report_pairs_pre_and_post(app):
    with app.app_context():
        pre_answers = {q["id"]: q["correct_index"] for q in surveys.SURVEY_QUESTIONS}
        wrong_answers = {q["id"]: (q["correct_index"] + 1) % len(q["options"]) for q in surveys.SURVEY_QUESTIONS}

        surveys.submit_survey("session-3", "pre", wrong_answers)
        surveys.submit_survey("session-3", "post", pre_answers)

        report = build_comparative_report()
        assert report["summary"]["participants"] == 1
        row = report["rows"][0]
        assert row["session_id"] == "session-3"
        assert row["delta"] > 0
