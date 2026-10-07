import os

from flask import Flask

from app.extensions import db, migrate, login_manager
from config import config


def create_app(config_name: str | None = None) -> Flask:
    if config_name is None:
        config_name = os.environ.get("FLASK_CONFIG") or "default"

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    from app.main import bp as main_bp
    from app.auth import bp as auth_bp
    from app.admin import bp as admin_bp
    from app.classes import bp as classes_bp
    from app.content import bp as content_bp
    from app.chat import bp as chat_bp
    from app.quiz import bp as quiz_bp
    from app.dojo import bp as dojo_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(classes_bp)
    app.register_blueprint(content_bp, url_prefix="/content")
    app.register_blueprint(chat_bp, url_prefix="/chat")
    app.register_blueprint(quiz_bp, url_prefix="/quiz")
    app.register_blueprint(dojo_bp, url_prefix="/dojo")

    # Ensure models are imported so Alembic autogenerate can see them,
    # and the user_loader callback is registered.
    from app import models  # noqa: F401

    # Register custom CLI commands
    from app.cli import register_cli_commands
    register_cli_commands(app)

    return app
