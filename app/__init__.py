"""Factory de la aplicacion Flask."""

from __future__ import annotations

import logging
from pathlib import Path

from flask import Flask, render_template

from .config import Config
from .extensions import bcrypt, db, jwt


def create_app(config_class: type[Config] = Config) -> Flask:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
    )
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )
    app.config.from_object(config_class)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    bcrypt.init_app(app)
    jwt.init_app(app)

    from . import auth, main, perfil  # noqa: WPS433

    app.register_blueprint(main.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(perfil.bp)

    @app.errorhandler(404)
    def _404(exc):  # noqa: ANN001
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def _500(exc):  # noqa: ANN001
        return render_template("errors/500.html"), 500

    with app.app_context():
        db.create_all()

    return app
