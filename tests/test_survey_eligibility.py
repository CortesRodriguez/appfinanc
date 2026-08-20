"""Tests del umbral de elegibilidad del Instrumento 1.

La encuesta se ofrece únicamente a personas con cuenta y con al menos
SURVEY_THRESHOLD `InstrumentVisit` registrados. Anónimos, siempre no elegibles.
"""

from src.auth.models import User
from src.constants import SURVEY_THRESHOLD
from src.evaluation.eligibility import is_eligible_for_survey, instrument_visit_count
from src.evaluation.models import InstrumentVisit
from src.extensions import db


def _make_user(app, email="ximena@example.cl"):
    user = User(username="ximena", email=email, password_hash="x")
    db.session.add(user)
    db.session.commit()
    return user


def _log_visits(user_id, n):
    for i in range(n):
        db.session.add(InstrumentVisit(user_id=user_id, instrument=f"ITEM{i}.SN"))
    db.session.commit()


def test_anonymous_user_is_never_eligible(app):
    with app.app_context():
        assert is_eligible_for_survey(None) is False


def test_zero_visits_not_eligible(app):
    with app.app_context():
        user = _make_user(app)
        assert instrument_visit_count(user.id) == 0
        assert is_eligible_for_survey(user.id) is False


def test_below_threshold_not_eligible(app):
    with app.app_context():
        user = _make_user(app)
        _log_visits(user.id, SURVEY_THRESHOLD - 1)
        assert is_eligible_for_survey(user.id) is False


def test_at_threshold_is_eligible(app):
    with app.app_context():
        user = _make_user(app)
        _log_visits(user.id, SURVEY_THRESHOLD)
        assert is_eligible_for_survey(user.id) is True


def test_above_threshold_still_eligible(app):
    with app.app_context():
        user = _make_user(app)
        _log_visits(user.id, SURVEY_THRESHOLD + 7)
        assert is_eligible_for_survey(user.id) is True


def test_eligibility_is_per_user(app):
    """La elegibilidad de A no arrastra a B: se cuenta por cuenta."""
    with app.app_context():
        user_a = _make_user(app, email="a@example.cl")
        user_b = _make_user(app, email="b@example.cl")
        _log_visits(user_a.id, SURVEY_THRESHOLD)
        assert is_eligible_for_survey(user_a.id) is True
        assert is_eligible_for_survey(user_b.id) is False
