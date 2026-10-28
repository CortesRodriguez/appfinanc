import os

import pytest
from sqlalchemy.engine import make_url

FLASK_SECRET_KEY_FALLBACK = "clave-solo-para-tests"
os.environ.setdefault("FLASK_SECRET_KEY", FLASK_SECRET_KEY_FALLBACK)

# Los tests corren contra PostgreSQL, el mismo motor que produccion. Cada test
# hace create_all/drop_all, asi que se exige una base dedicada cuyo nombre
# termine en "_test" para no borrar datos reales por accidente.
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
if not TEST_DATABASE_URL:
    raise RuntimeError(
        "Define TEST_DATABASE_URL con una base PostgreSQL dedicada a tests, p. ej. "
        "postgresql+psycopg://usuario:clave@localhost:5432/appfint_test"
    )
_test_db_name = make_url(TEST_DATABASE_URL).database or ""
if not _test_db_name.endswith("_test"):
    raise RuntimeError(
        f"TEST_DATABASE_URL apunta a '{_test_db_name}': el nombre debe terminar en '_test' "
        "porque cada test borra todas las tablas."
    )
# Se fija antes de importar `config`, que lee DATABASE_URL al cargarse.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from config import Config  # noqa: E402
from src.extensions import db  # noqa: E402
from src.web import create_app  # noqa: E402


class TestConfig(Config):
    SQLALCHEMY_DATABASE_URI = Config.SQLALCHEMY_DATABASE_URI
    TESTING = True
    # Los tests no invocan FinBERT (cargar el modelo agrega ~3-5 s por test).
    # La lógica de FinBERT + fallback se cubre por separado en test_explainer.py.
    USE_FINBERT = False
    # Sin esto, un USE_LLM=true en .env haria que los tests llamen a Groq de verdad
    # (lento, consume cuota y el texto deja de ser determinista).
    USE_LLM = False


@pytest.fixture
def app():
    application = create_app(TestConfig)
    with application.app_context():
        db.create_all()
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()
