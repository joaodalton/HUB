import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
(BASE_DIR / 'database').mkdir(parents=True, exist_ok=True)

load_dotenv(BASE_DIR / ".env")

class Config:
    API_PORT = int(os.getenv('API_PORT', '8000'))
    DEBUG = os.getenv('FLASK_DEBUG', 'true').lower() == 'true'
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
    # Usada por utils/crypto.py pra criptografar o refresh token do GoogleAccount.
    # Gerar com: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    SECRET_ENCRYPTION_KEY = os.getenv('SECRET_ENCRYPTION_KEY', '')
    # Usada por utils/auth.py pra assinar o token de login. Chave diferente da de cima
    # de proposito -- nunca reaproveitar a mesma chave pra dois usos criptograficos distintos.
    # Gerar com: python -c "import secrets; print(secrets.token_hex(32))"
    SECRET_KEY = os.getenv('SECRET_KEY', '')
    SQLALCHEMY_DATABASE_URI = os.getenv(
    'DATABASE_URL',
    f"sqlite:///{(BASE_DIR / 'database' / 'hub.db').as_posix()}" 
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False