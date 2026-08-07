from flask import Flask
from flask_cors import CORS

from config import Config
from extensions import db, migrate, limiter


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)

    from models.client import Client
    from models.plant import Plant
    from models.consumer_unit import ConsumerUnit, PlantConnection
    from models.category import Category
    from models.document import Document
    from models.setting import Setting
    from models.google_account import GoogleAccount
    from models.log_entry import LogEntry
    from models.pendencia import Pendencia, PendenciaComentario
    from models.user import User

    CORS(app, origins=[Config.FRONTEND_URL], supports_credentials=True)

    from routes.auth_routes import auth_routes
    from routes.config_routes import config_routes
    from routes.drive_routes import drive_routes
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

    app.register_blueprint(health_routes)
    app.register_blueprint(auth_routes)
    app.register_blueprint(drive_routes)
    app.register_blueprint(config_routes)
    app.register_blueprint(client_routes)
    app.register_blueprint(plant_routes)
    app.register_blueprint(uc_routes)
    app.register_blueprint(document_routes)
    app.register_blueprint(category_routes)
    app.register_blueprint(settings_routes)
    app.register_blueprint(oauth_routes)
    app.register_blueprint(log_routes)
    app.register_blueprint(pendencia_routes)

    from utils.auth import register_auth_middleware
    register_auth_middleware(app, public_paths={
        '/', '/api/v1/auth/login', '/api/v1/auth/bootstrap', '/api/v1/auth/logout',
        '/api/v1/oauth/google/authorize', '/api/v1/oauth/google/callback'
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