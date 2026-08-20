import sentry_sdk
from flask import Flask
from flask_cors import CORS
from sentry_sdk.integrations.flask import FlaskIntegration

from config import Config
from extensions import db, migrate, limiter


def create_app() -> Flask:
    # Sem DSN configurado, sentry_sdk.init vira no-op -- seguro rodar local
    # sem nenhuma variavel setada (dev nao manda erro nenhum pro Sentry por
    # padrao). send_default_pii=False de proposito: nunca manda dado pessoal
    # (email, IP) junto do erro sem decisao explicita depois.
    if Config.SENTRY_DSN:
        sentry_sdk.init(
            dsn=Config.SENTRY_DSN,
            environment=Config.SENTRY_ENVIRONMENT,
            integrations=[FlaskIntegration()],
            traces_sample_rate=0.1,
            send_default_pii=False
        )

    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)

    from models.empresa import Empresa  # type: ignore
    from models.client import Client  # type: ignore
    from models.plant import Plant  # type: ignore
    from models.consumer_unit import ConsumerUnit, PlantConnection  # type: ignore
    from models.category import Category  # type: ignore
    from models.document import Document  # type: ignore
    from models.setting import Setting  # type: ignore
    from models.google_account import GoogleAccount  # type: ignore
    from models.log_entry import LogEntry  # type: ignore
    from models.pendencia import Pendencia, PendenciaComentario  # type: ignore
    from models.user import User  # type: ignore
    from models.invitation import Invitation  # type: ignore
    from models.rateio_historico import RateioHistorico  # type: ignore
    from models.password_reset_token import PasswordResetToken  # type: ignore

    CORS(app, origins=[Config.FRONTEND_URL], supports_credentials=True)

    from routes.auth_routes import auth_routes
    from routes.config_routes import config_routes
    from routes.drive_routes import drive_routes
    from routes.empresa_routes import empresa_routes
    from routes.health_routes import health_routes
    from routes.client_routes import client_routes
    from routes.plant_routes import plant_routes
    from routes.uc_routes import uc_routes
    from routes.document_routes import document_routes
    from routes.category_routes import category_routes
    from routes.settings_routes import settings_routes
    from routes.oauth_routes import oauth_routes
    from routes.log_routes import log_routes
    from routes.pendencia_routes import pendencia_routes
    from routes.user_routes import user_routes
    from routes.invitation_routes import invitation_routes
    from routes.rateio_routes import rateio_routes
    from routes.platform_routes import platform_routes

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
    app.register_blueprint(invitation_routes)
    app.register_blueprint(rateio_routes)
    app.register_blueprint(platform_routes)

    from utils.auth import register_auth_middleware
    register_auth_middleware(app, public_paths={
        '/', '/api/v1/auth/login', '/api/v1/auth/bootstrap', '/api/v1/auth/logout',
        '/api/v1/auth/register', '/api/v1/auth/aceitar-convite',
        '/api/v1/convites/verificar',
        '/api/v1/empresas/registro',
        '/api/v1/oauth/google/authorize', '/api/v1/oauth/google/callback',
        '/api/v1/auth/esqueci-senha', '/api/v1/auth/redefinir-senha'
    }, public_path_prefixes={
        # request.path e' o path LITERAL da requisicao (ex.: /api/v1/empresas/select),
        # nunca a string do padrao de rota com <string:slug> -- por isso essa rota
        # nunca cai no set exato acima. Prefixo dedicado, checado a parte.
        '/api/v1/empresas/'
    })

    @app.after_request
    def _set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        if not Config.DEBUG:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response

    return app


app = create_app()


if __name__ == '__main__':
    app.run(port=Config.API_PORT, debug=Config.DEBUG)