import pytest

from config import Config
from src.extensions import db
from src.web import create_app


class TestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    TESTING = True
    # Los tests no invocan FinBERT (cargar el modelo agrega ~3-5 s por test).
    # La lógica de FinBERT + fallback se cubre por separado en test_explainer.py.
    USE_FINBERT = False


@pytest.fixture
def app():
    application = create_app(TestConfig)
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()
