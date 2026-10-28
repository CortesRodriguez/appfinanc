import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()


def _require_env(var):
    val = os.environ.get(var)
    if not val:
        raise RuntimeError(
            f"Variable de entorno requerida '{var}' no configurada. "
            "Ejecuta: cp .env.example .env"
        )
    return val


def _database_url():
    """URL de PostgreSQL desde DATABASE_URL (obligatoria).

    Los PaaS entregan `postgres://` o `postgresql://`; se normaliza al driver
    psycopg 3 (`postgresql+psycopg://`). Cualquier otro motor se rechaza.
    """
    url = _require_env("DATABASE_URL")
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            url = "postgresql+psycopg://" + url[len(prefix):]
            break
    if not url.startswith("postgresql+psycopg://"):
        raise RuntimeError(
            "DATABASE_URL debe ser una URL de PostgreSQL "
            "(postgresql+psycopg://usuario:clave@host:5432/base)."
        )
    return url


class Config:
    SECRET_KEY = _require_env("FLASK_SECRET_KEY")
    # PostgreSQL como unico motor: escrituras concurrentes de varios workers y
    # datos que sobreviven a los redespliegues. pool_pre_ping/pool_recycle
    # descartan conexiones cerradas por el servidor gestionado antes de usarlas.
    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 1800}
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # RF-17.2, RNF-09.2: sesion mediante JWT en cookie httpOnly, expira a las 24 horas
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY") or SECRET_KEY
    JWT_TOKEN_LOCATION = ["cookies"]
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    JWT_COOKIE_SECURE = os.environ.get("JWT_COOKIE_SECURE", "true").lower() == "true"
    JWT_COOKIE_SAMESITE = "Lax"
    JWT_COOKIE_CSRF_PROTECT = True
    JWT_CSRF_IN_COOKIES = True

    # RNF-05.1: largo minimo y maximo de contrasena. El tope es de 64 caracteres;
    # ademas el servicio exige <= 72 bytes UTF-8, que es lo que bcrypt acepta.
    PASSWORD_MIN_LENGTH = 8
    PASSWORD_MAX_LENGTH = 64

    # Bloqueo anti fuerza bruta del login: tras N intentos fallidos seguidos
    # para un mismo correo, la cuenta no acepta intentos por LOGIN_LOCK_MINUTES.
    LOGIN_MAX_ATTEMPTS = 5
    LOGIN_LOCK_MINUTES = 15

    # Login/registro con Google (OAuth2/OIDC). Vacio = boton de Google no se registra.
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")

    ALPHAVANTAGE_API_KEY = os.environ.get("ALPHAVANTAGE_API_KEY", "")

    # LLM generativo (Groq / qwen/qwen3.8-27b): cuando USE_LLM=true y
    # GROQ_API_KEY está configurado, las explicaciones se generan en tiempo real
    # con un modelo de lenguaje en lugar de plantillas predefinidas. Degradación
    # silenciosa a plantillas si falla (RNF-09).
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
    USE_LLM = os.environ.get("USE_LLM", "false").lower().strip(".").strip() == "true"

    # RF-04.1: FinBERT es opcional y solo aporta la etiqueta de sentimiento; el
    # texto lo redacta el LLM o las plantillas. Desactivado por defecto porque
    # `transformers`/`torch` no estan en requirements.txt. Si se activa y no
    # estan instalados, degrada en silencio (`src/nlp/explainer.py:_finbert_signal`),
    # coherente con la tolerancia a fallos de RNF-09.
    USE_FINBERT = os.environ.get("USE_FINBERT", "false").lower() == "true"

    # RNF-02.2: cache de indicadores extraidos por 5 minutos
    CACHE_TTL_SECONDS = 5 * 60

    # Noticias de la portada (Google News RSS): cache largo para no repetir consultas
    NEWS_CACHE_TTL_SECONDS = 20 * 60
    NEWS_MAX_ITEMS = 5

    # RNF-01.1: tiempo maximo esperado por explicacion (informativo, usado en logging)
    MAX_RESPONSE_SECONDS = 5

    # RF-10.1: cantidad de consultas que muestra el historial del perfil
    HISTORY_MAX_ITEMS = 50

    # RNF-08.2: reintentos ante falla de conexion con APIs financieras
    API_MAX_RETRIES = 3

    # En desarrollo: forzar al navegador a revalidar JS/CSS en cada carga para
    # que los cambios en estaticos se reflejen sin necesidad de hard-refresh.
    # En produccion se subiria a un caching largo con hash en el filename.
    SEND_FILE_MAX_AGE_DEFAULT = 0
