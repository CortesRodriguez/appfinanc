"""Modulo Presentador (RF-07 a RF-10): aplicacion Flask."""

from flask import Flask

from config import Config
from src.extensions import bcrypt, db, jwt


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)
    bcrypt.init_app(app)
    jwt.init_app(app)

    from src.auth.models import RevokedToken, User

    @jwt.token_in_blocklist_loader
    def _is_token_revoked(jwt_header, jwt_payload):  # noqa: ARG001
        return db.session.get(RevokedToken, jwt_payload["jti"]) is not None

    @app.context_processor
    def _inject_current_user():
        from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

        try:
            verify_jwt_in_request(optional=True)
            user_id = get_jwt_identity()
            current_user = db.session.get(User, int(user_id)) if user_id else None
        except Exception:  # noqa: BLE001 - token invalido/expirado: se navega como anonimo
            current_user = None

        return {"current_user": current_user}

    from . import routes
    from src.auth import routes as auth_routes
    from src.profile import routes as profile_routes

    app.register_blueprint(routes.bp)
    app.register_blueprint(auth_routes.bp)
    app.register_blueprint(profile_routes.bp)

    # Filtro Jinja usado por el historial de consultas (RF-02.2) para
    # mostrar la fecha/hora en formato "13:25:45 - 28 de agosto de 2026".
    app.jinja_env.filters["es_datetime"] = routes._format_datetime_es

    with app.app_context():
        db.create_all()

    return app
