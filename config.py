import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class Config:
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'appfint.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # RF-17.2, RNF-09.2: sesion mediante JWT en cookie httpOnly, expira a las 24 horas
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", os.environ.get("FLASK_SECRET_KEY", "dev-jwt-secret-cambiar-en-produccion"))
    JWT_TOKEN_LOCATION = ["cookies"]
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    JWT_COOKIE_SECURE = os.environ.get("JWT_COOKIE_SECURE", "false").lower() == "true"
    JWT_COOKIE_SAMESITE = "Lax"
    JWT_COOKIE_CSRF_PROTECT = True
    JWT_CSRF_IN_COOKIES = True

    # RNF-09.1: largo minimo de contrasena
    PASSWORD_MIN_LENGTH = 8

    ALPHAVANTAGE_API_KEY = os.environ.get("ALPHAVANTAGE_API_KEY", "")

    # RF-04.1: FinBERT es el componente NLP central del Procesador. Activado por
    # defecto. Si `transformers`/`torch` no están instalados o la carga del
    # modelo falla, el sistema degrada silenciosamente al motor de plantillas
    # puras (ver `src/nlp/explainer.py:_finbert_signal`), coherente con la
    # tolerancia a fallos de RNF-09.
    USE_FINBERT = os.environ.get("USE_FINBERT", "true").lower() == "true"

    # RNF-02.2: cache de indicadores extraidos por 5 minutos
    CACHE_TTL_SECONDS = 5 * 60

    # RNF-01.1: tiempo maximo esperado por explicacion (informativo, usado en logging)
    MAX_RESPONSE_SECONDS = 5

    # RF-10.1: historial limitado a las ultimas 5 consultas de la sesion
    HISTORY_MAX_ITEMS = 5

    # RNF-08.2: reintentos ante falla de conexion con APIs financieras
    API_MAX_RETRIES = 3

    # En desarrollo: forzar al navegador a revalidar JS/CSS en cada carga para
    # que los cambios en estaticos se reflejen sin necesidad de hard-refresh.
    # En produccion se subiria a un caching largo con hash en el filename.
    SEND_FILE_MAX_AGE_DEFAULT = 0
