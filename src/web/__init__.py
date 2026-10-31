"""Modulo Presentador (RF-07 a RF-10): aplicacion Flask."""

from flask import Flask

from config import Config
from src.extensions import bcrypt, db, jwt, migrate, oauth


def _register_error_handlers(app):
    """Las rutas /api/* responden siempre JSON, tambien cuando algo falla.

    Sin esto, una excepcion no prevista devuelve una pagina HTML de error y el
    navegador la intenta leer como JSON ("Unexpected token '<'"), que no le dice
    nada a quien usa la app. Las paginas normales conservan su respuesta HTML.
    """
    from flask import jsonify, request
    from werkzeug.exceptions import HTTPException

    messages = {
        404: "No encontramos lo que buscas.",
        405: "Esa acción no está permitida.",
        429: "Hiciste muchas solicitudes seguidas. Espera un momento e inténtalo de nuevo.",
    }

    @app.errorhandler(Exception)
    def _json_errors_for_api(exc):
        if not request.path.startswith("/api/"):
            if isinstance(exc, HTTPException):
                return exc
            raise exc
        if isinstance(exc, HTTPException):
            status = exc.code or 500
            message = messages.get(status, exc.description if status < 500 else None)
        else:
            from src.extensions import db

            db.session.rollback()
            app.logger.exception("Error no controlado en %s", request.path)
            status, message = 500, None
        return jsonify({"error": message or "Algo salió mal de nuestro lado. Inténtalo de nuevo en unos minutos."}), status


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    jwt.init_app(app)
    oauth.init_app(app)

    if app.config.get("GOOGLE_CLIENT_ID"):
        oauth.register(
            name="google",
            client_id=app.config["GOOGLE_CLIENT_ID"],
            client_secret=app.config["GOOGLE_CLIENT_SECRET"],
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )

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

        return {
            "current_user": current_user,
            "google_oauth_enabled": bool(app.config.get("GOOGLE_CLIENT_ID")),
        }

    _register_error_handlers(app)

    from . import routes
    from src.auth import routes as auth_routes
    from src.profile import routes as profile_routes

    app.register_blueprint(routes.bp)
    app.register_blueprint(auth_routes.bp)
    app.register_blueprint(profile_routes.bp)

    # Filtro Jinja usado por el historial de consultas (RF-02.2) para
    # mostrar la fecha/hora en formato "13:25:45 - 28 de agosto de 2026".
    app.jinja_env.filters["es_datetime"] = routes._format_datetime_es

    return app
