"""Instancias compartidas de Flask.

Se declaran fuera de la factory para poder importarlas desde blueprints
y modelos sin generar ciclos.
"""

from __future__ import annotations

from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
bcrypt = Bcrypt()
jwt = JWTManager()
