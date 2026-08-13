import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
(BASE_DIR / 'database').mkdir(parents=True, exist_ok=True)

load_dotenv(BASE_DIR / ".env")

class Config:

    API_PORT = int(os.getenv('API_PORT', '8000'))

    # Default seguro: se a variavel nao existir (ex.: esquecida no painel do Render),
    # cai em DEBUG=False, nao True. Falhar "fechado" -- local continua com debug
    # porque backend/.env ja seta FLASK_DEBUG=true explicitamente (.env.example).
    DEBUG = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'

    DATA_PROVIDER = os.getenv('DATA_PROVIDER', 'google_drive')

    GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", str(BASE_DIR / "credentials.json"))

    GOOGLE_DRIVE_ROOT_FOLDER_ID = os.getenv('GOOGLE_DRIVE_ROOT_FOLDER_ID', '')

    GOOGLE_DRIVE_DATA_FILE = os.getenv('GOOGLE_DRIVE_DATA_FILE', 'hub-data.json')

    GOOGLE_DRIVE_SCOPES = os.getenv(
        'GOOGLE_DRIVE_SCOPES',
        'https://www.googleapis.com/auth/drive.readonly'
    ).split(',')

    # OAuth 2.0 de usuario real (substitui/complementa o credentials.json de service account).
    # Client ID/Secret vem do Google Cloud Console -- ver README pra passo a passo.
    GOOGLE_OAUTH_CLIENT_ID = os.getenv('GOOGLE_OAUTH_CLIENT_ID', '')

    GOOGLE_OAUTH_CLIENT_SECRET = os.getenv('GOOGLE_OAUTH_CLIENT_SECRET', '')

    GOOGLE_OAUTH_REDIRECT_URI = os.getenv('GOOGLE_OAUTH_REDIRECT_URI', 'http://localhost:8000/api/v1/oauth/google/callback')

    # Pra onde redirecionar de volta depois do callback do Google (a SPA do frontend, nao o backend).
    FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:5173')

    SQL_DRIVER = os.getenv('SQL_DRIVER', '')

    SQL_HOST = os.getenv('SQL_HOST', '')

    SQL_PORT = os.getenv('SQL_PORT', '')

    SQL_DATABASE = os.getenv('SQL_DATABASE', '')

    SQL_USER = os.getenv('SQL_USER', '')

    SQL_PASSWORD = os.getenv('SQL_PASSWORD', '')

    # "Senha da familia" pro auto-cadastro na tela de login (POST /auth/register).
    # Vazio = auto-cadastro desligado (padrao seguro -- ninguem se cadastra sozinho
    # sem essa variavel configurada de proposito). Quem se auto-cadastra SEMPRE
    # vira 'viewer' (so leitura), nunca admin -- isso e forcado no backend,
    # independente do que o formulario mandar (ver services/user_service.py).
    SIGNUP_CODE = os.getenv('SIGNUP_CODE', '')

    # Usada por utils/crypto.py pra criptografar o refresh token do GoogleAccount.
    # Gerar com: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    SECRET_ENCRYPTION_KEY = os.getenv('SECRET_ENCRYPTION_KEY', '')

    # Usada por utils/auth.py pra assinar o token de login. Chave diferente da de cima
    # de proposito -- nunca reaproveitar a mesma chave pra dois usos criptograficos distintos.
    # Gerar com: python -c "import secrets; print(secrets.token_hex(32))"
    SECRET_KEY = os.getenv('SECRET_KEY', '')
    # DSN do projeto backend no Sentry (sentry.io) -- vazio desliga o rastreamento
    # de erro por completo, sem quebrar nada (sentry_sdk.init com dsn=None e no-op).
    SENTRY_DSN = os.getenv('SENTRY_DSN', '')
    SENTRY_ENVIRONMENT = os.getenv('SENTRY_ENVIRONMENT', 'development')

    SQLALCHEMY_DATABASE_URI = os.getenv(
    'DATABASE_URL',
    f"sqlite:///{(BASE_DIR / 'database' / 'hub.db').as_posix()}" 
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Neon (e Postgres gerenciado em geral) derruba conexao ociosa por conta propria
    # (Neon free suspende o compute depois de alguns minutos parado). Sem isso, a
    # proxima query reusa uma conexao morta do pool e cai com "SSL connection has
    # been closed unexpectedly". pool_pre_ping testa a conexao (SELECT 1 leve) antes
    # de cada uso e troca por uma nova se estiver morta -- transparente pra aplicacao.
    # pool_recycle forca renovacao antes mesmo de morrer (280s, abaixo do timeout do Neon).
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 280
    }