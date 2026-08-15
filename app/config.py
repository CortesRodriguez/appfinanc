"""Configuracion de la aplicacion Flask.

Concentra los parametros relacionados con base de datos, sesion y
seguridad. En un entorno real la SECRET_KEY y el JWT_SECRET_KEY se
leerian desde variables de entorno; aca se generan defaults seguros
para el prototipo academico y se permite sobrescribirlos por env.
"""

from __future__ import annotations

import os
import secrets
from datetime import timedelta
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_DB_PATH = _ROOT / "instance" / "appfinanc.sqlite"


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get("DATABASE_URL") or f"sqlite:///{_DB_PATH}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # RNF-06.2: expiracion de 24 horas para los JWT.
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY") or secrets.token_hex(32)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    JWT_TOKEN_LOCATION = ["cookies"]
    JWT_COOKIE_SECURE = False  # dev/local
    JWT_COOKIE_CSRF_PROTECT = False
    JWT_ACCESS_COOKIE_NAME = "appfinanc_access"
    JWT_COOKIE_SAMESITE = "Lax"

    # RNF-06.1: largo minimo de la contraseña se valida en el registro.
    MIN_PASSWORD_LEN = 8

    # RF-10.1: cantidad de consultas mostradas en el historial de sesion.
    HISTORIAL_MAX = 5

    # Metodologia de evaluacion: encuesta al llegar a 5 consultas.
    UMBRAL_ENCUESTA = 5
