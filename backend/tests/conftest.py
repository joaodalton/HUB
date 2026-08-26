# backend/tests/conftest.py
"""
App factory de teste — cria uma Flask app com banco SQLite totalmente
isolado, sem passar pelo create_app() de produção que lê .env e conecta
ao Neon antes de qualquer override.
"""
import os
import tempfile
import uuid

import pytest
from werkzeug.security import generate_password_hash

_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in os.sys.path:
    os.sys.path.insert(0, _backend_dir)


def create_test_app():
    """Cria uma Flask app de teste com SQLite em arquivo temporário."""
    from flask import Flask
    from flask_cors import CORS
    from extensions import db, migrate, limiter
    from utils.auth import register_auth_middleware

    tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp_db.close()

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{tmp_db.name}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = "test-secret-do-not-use-in-prod"
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["RATELIMIT_ENABLED"] = False
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["DEBUG"] = True

    db.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)

    CORS(app, origins=['http://localhost:5173', 'http://127.0.0.1:5173',
                       'https://hub.local'], supports_credentials=True)

    # Blueprints
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
    from routes.bulk_import_export_routes import bulk_routes
    from routes.email_template_routes import email_template_routes
    from routes.fatura_routes import fatura_routes

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
    app.register_blueprint(bulk_routes)
    app.register_blueprint(email_template_routes)
    app.register_blueprint(fatura_routes)

    # Auth middleware
    register_auth_middleware(
        app,
        public_paths={
            '/', '/api/v1/auth/login', '/api/v1/auth/bootstrap', '/api/v1/auth/logout',
            '/api/v1/auth/register', '/api/v1/auth/aceitar-convite',
            '/api/v1/convites/verificar',
            '/api/v1/oauth/google/authorize', '/api/v1/oauth/google/callback',
            '/api/v1/auth/esqueci-senha', '/api/v1/auth/redefinir-senha',
            '/api/v1/faturas/webhook/asaas',
        },
        public_path_prefixes=set(),
    )

    # Cria tabelas e dados iniciais
    with app.app_context():
        db.create_all()

        from models.user import User
        from models.empresa import Empresa

        empresa = Empresa(nome="Empresa de Teste", cnpj="12345678901234")
        empresa.slug = f"empresa-de-teste-{uuid.uuid4().hex[:8]}"
        db.session.add(empresa)
        db.session.flush()

        admin = User(
            email="admin@example.com",
            password_hash=generate_password_hash("admin123"),
            role="admin", is_platform_admin=True, empresa_id=empresa.id,
        )
        db.session.add(admin)
        db.session.flush()

        normal = User(
            email="normal@example.com",
            password_hash=generate_password_hash("senha123"),
            role="member", is_platform_admin=False, empresa_id=empresa.id,
        )
        db.session.add(normal)
        db.session.commit()

    def cleanup():
        try:
            os.unlink(tmp_db.name)
        except OSError:
            pass

    return app, cleanup


@pytest.fixture(scope="session")
def test_app():
    """App de teste configurada com SQLite temporário."""
    app, cleanup = create_test_app()
    yield app
    cleanup()


@pytest.fixture(scope="function")
def client(test_app):
    """Retorna test_client padrão do Flask."""
    with test_app.test_client() as c:
        yield c


@pytest.fixture(scope="function")
def db_session(test_app):
    """Sessão SQLAlchemy de teste."""
    with test_app.app_context():
        from extensions import db
        yield db.session


# Helpers -----------------------------------------------------------------


def login_as(client, email: str, senha: str):
    """Faz login e retorna (client, csrf_token). O client já tem cookies."""
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "senha": senha},
    )
    assert resp.status_code == 200, f"Login falhou para {email}: {resp.get_data(as_text=True)}"

    cookies = resp.headers.getlist("Set-Cookie")
    csrf = None
    for cookie in cookies:
        if "hub_csrf=" in cookie:
            csrf = cookie.split("hub_csrf=")[-1].split(";")[0]
            break

    assert csrf is not None, "CSRF token não encontrado no login"
    return client, csrf


def criar_empresa(client, nome: str, csrf: str,
                  owner_nome: str = "Admin", owner_senha: str = "admin123"):
    """Cria uma empresa via POST /empresas. Retorna o ID.

    O email do owner é gerado aleatoriamente por padrão para evitar conflito
    de UNIQUE no banco de teste (scope=session, persiste entre testes).
    """
    resp = client.post(
        "/api/v1/empresas",
        json={
            "empresa": {"nome": nome},
            "owner": {"nome": owner_nome, "email": f"owner-{uuid.uuid4().hex[:8]}@teste.com", "senha": owner_senha},
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code in (200, 201), f"Falha ao criar empresa: {resp.status_code} {resp.get_data(as_text=True)}"
    data = resp.get_json()
    return data.get("data", data).get("empresa", data).get("id")


def extrair_empresa_id(resp):
    """Extrai ID da empresa da resposta (suporta formato envolto em 'data'/'empresa')."""
    data = resp.get_json()
    if data is None:
        return None
    if isinstance(data, dict):
        # {"data": {"empresa": {"id": ...}}, ...}
        if "data" in data:
            inner = data["data"]
            if isinstance(inner, dict):
                if "empresa" in inner and isinstance(inner["empresa"], dict):
                    return inner["empresa"].get("id")
                if "id" in inner:
                    return inner["id"]
        # Fallback direto
        if "id" in data:
            return data["id"]
        if "empresa" in data and isinstance(data["empresa"], dict):
            return data["empresa"].get("id")
    return None
