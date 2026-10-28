"""Extensiones compartidas (evita imports circulares entre web y evaluation)."""

from authlib.integrations.flask_client import OAuth
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
migrate = Migrate()
bcrypt = Bcrypt()
jwt = JWTManager()
oauth = OAuth()
