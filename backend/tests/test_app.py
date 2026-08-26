# backend/tests/test_app.py
"""
App factory de teste — cria uma Flask app com banco SQLite totalmente
isolado, sem passar pelo create_app() de produção que lê .env e conecta
ao Neon antes de qualquer override ser possível.

Uso: conftest.py importa _create_test_app(db_uri) e o usa no fixture
'session' de app, em vez de create_app() do app.py.
"""

from __future__ import annotations

from flask import Flask
from flask_cors import CORS

from extensions import db, limiter  # type: ignore
from utils.auth import register_auth_middleware  # type: ignore


def _create_test_app(db_uri: str) -> Flask:
    """Cria uma Flask app de teste com banco SQLite.

    A ordem é importante: configuramos SQLALCHEMY_DATABASE_URI ANTES de
    db.init_app(), para que o engine SQLAlchemy use nosso SQLite e não o
    Neon do .env.
    """
    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        RATELIMIT_ENABLED=False,
        SQLALCHEMY_DATABASE_URI=db_uri,
        SQLALCHEMY_ENGINE_OPTIONS={
            "pool_pre_ping": True,
            "pool_recycle": 280,
        },
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )

    db.init_app(app)
    limiter.init_app(app)

    # Blueprints — mesma lista que o create_app() de produção, para que
    # os testes executem contra a mesma superfície de rotas.
    from routes.auth_routes import auth_routes  # noqa: E402
    from routes.client_routes import client_routes  # noqa: E402
    from routes.empresa_routes import empresa_routes  # noqa: E402
    from routes.health_routes import health_routes  # noqa: E402
    from routes.uc_routes import uc_routes  # noqa: E402
    from routes.plant_routes import plant_routes  # noqa: E402
    from routes.category_routes import category_routes  # noqa: E402
    from routes.settings_routes import settings_routes  # noqa: E402
    from routes.oauth_routes import oauth_routes  # noqa: E402
    from routes.log_routes import log_routes  # noqa: E402
    from routes.pendencia_routes import pendencia_routes  # noqa: E402
    from routes.user_routes import user_routes  # noqa: E402
    from routes.invitation_routes import invitation_routes  # noqa: E402
    from routes.rateio_routes import rateio_routes  # noqa: E402
    from routes.bulk_import_export_routes import bulk_routes  # noqa: E402
    from routes.email_template_routes import email_template_routes  # noqa: E402
    from routes.fatura_routes import fatura_routes  # noqa: E402
    from routes.config_routes import config_routes  # noqa: E402
    from routes.drive_routes import drive_routes  # noqa: E402
    from routes.document_routes import document_routes  # noqa: E402

    app.register_blueprint(health_routes)
    app.register_blueprint(auth_routes)
    app.register_blueprint(drive_routes)
    app.register_blueprint(config_routes)
    app.register_blueprint(empresa_routes)
    app.register_blueprint(client_routes)
    app.register_blueprint(plant_routes)
    app.register_blueprint(uc_routes)
    app.register_blueprint(document_routes)
    app.register_blueprint(category_routes)
    app.register_blueprint(settings_routes)
    app.register_blueprint(oauth_routes)
    app.register_blueprint(log_routes)
    app.register_blueprint(pendencia_routes)
    app.register_blueprint(user_routes)
    app.register_blueprint(email_template_routes)
    app.register_blueprint(fatura_routes)
    app.register_blueprint(invitation_routes)
    app.register_blueprint(rateio_routes)
    app.register_blueprint(bulk_routes)

    # CORS — mesma configuração de produção.
    CORS(
        app,
        origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "https://hub.local",
        ],
        supports_credentials=True,
    )

    # Middleware de auth — mesma configuração de produção.
    register_auth_middleware(
        app,
        public_paths={
            "/",
            "/api/v1/auth/login",
            "/api/v1/auth/bootstrap",
            "/api/v1/auth/logout",
            "/api/v1/auth/register",
            "/api/v1/auth/aceitar-convite",
            "/api/v1/convites/verificar",
            "/api/v1/auth/esqueci-senha",
            "/api/v1/auth/redefinir-senha",
        },
        public_path_prefixes=set(),
    )

    # Security headers — mesma configuração de produção.
    @app.after_request
    def _set_security_headers(response):  # noqa: F811
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    return app
