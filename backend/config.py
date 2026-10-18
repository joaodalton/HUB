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

    # OAuthlib recusa HTTP por padrão. Desenvolvimento local pode habilitar a
    # exceção oficial somente de forma explícita, nunca por acidente ao ligar
    # FLASK_DEBUG em uma instância acessível pela rede.
    OAUTH_ALLOW_INSECURE_TRANSPORT = os.getenv('OAUTH_ALLOW_INSECURE_TRANSPORT', 'false').lower() == 'true'

    # Pra onde redirecionar de volta depois do callback do Google (a SPA do frontend, nao o backend).
    FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:5173')

    # B1 conserva ambiente por instalacao; API keys/tokens cifrados por empresa.
    ASAAS_API_BASE_URL = os.getenv('ASAAS_API_BASE_URL', 'https://api-sandbox.asaas.com/v3')
    # Compatibilidade de configuracao apenas: B2 NAO usa este token global.
    ASAAS_WEBHOOK_TOKEN = os.getenv('ASAAS_WEBHOOK_TOKEN', '')
    # Plataforma HUB: conta e webhook separados das credenciais ASAAS das empresas.
    PLATFORM_ASAAS_API_BASE_URL = os.getenv('PLATFORM_ASAAS_API_BASE_URL', 'https://api-sandbox.asaas.com/v3')
    PLATFORM_ASAAS_API_KEY = os.getenv('PLATFORM_ASAAS_API_KEY', '')
    PLATFORM_ASAAS_WEBHOOK_TOKEN = os.getenv('PLATFORM_ASAAS_WEBHOOK_TOKEN', '')

    # Novos PDFs de fatura: local somente em desenvolvimento/testes; R2 via S3 em producao.
    STORAGE_PROVIDER = os.getenv('STORAGE_PROVIDER', '')
    OBJECT_STORAGE_ENDPOINT = os.getenv('OBJECT_STORAGE_ENDPOINT', '')
    OBJECT_STORAGE_BUCKET = os.getenv('OBJECT_STORAGE_BUCKET', '')
    OBJECT_STORAGE_ACCESS_KEY_ID = os.getenv('OBJECT_STORAGE_ACCESS_KEY_ID', '')
    OBJECT_STORAGE_SECRET_ACCESS_KEY = os.getenv('OBJECT_STORAGE_SECRET_ACCESS_KEY', '')
    OBJECT_STORAGE_REGION = os.getenv('OBJECT_STORAGE_REGION', 'auto')
    OBJECT_STORAGE_LOCAL_DIR = os.getenv('OBJECT_STORAGE_LOCAL_DIR', str(BASE_DIR / 'database' / 'objects'))

    FATURA_CONCESSIONARIA_MAX_BYTES = int(os.getenv(
        'FATURA_CONCESSIONARIA_MAX_BYTES', str(10 * 1024 * 1024)
    ))
    FATURA_CONCESSIONARIA_MAX_PAGES = int(os.getenv(
        'FATURA_CONCESSIONARIA_MAX_PAGES', '10'
    ))
    BILLING_DIAGNOSTIC_TIMEOUT_SECONDS = int(os.getenv(
        'BILLING_DIAGNOSTIC_TIMEOUT_SECONDS', '20'
    ))
    # 100 MiB por arquivo ANEEL; limite exclusivo desta rota, em bytes.
    REGULATORY_TARIFF_MAX_BYTES = int(os.getenv('REGULATORY_TARIFF_MAX_BYTES', str(100 * 1024 * 1024)))
    REGULATORY_TARIFF_TEMP_DIR = os.getenv('REGULATORY_TARIFF_TEMP_DIR', '')
    REGULATORY_TARIFF_MAX_ROWS = int(os.getenv('REGULATORY_TARIFF_MAX_ROWS', '100000'))
    REGULATORY_TARIFF_PREVIEW_TTL_MINUTES = int(os.getenv('REGULATORY_TARIFF_PREVIEW_TTL_MINUTES', '20'))
    ANEEL_CKAN_API_URL = os.getenv('ANEEL_CKAN_API_URL', 'https://dadosabertos.aneel.gov.br/api/3/action')
    ANEEL_CKAN_TIMEOUT_SECONDS = int(os.getenv('ANEEL_CKAN_TIMEOUT_SECONDS', '15'))
    ANEEL_CKAN_TOKEN = os.getenv('ANEEL_CKAN_TOKEN', '')

    # Meta App e assinatura do webhook sao infraestrutura do HUB. O token de
    # acesso de cada numero fica cifrado por empresa em ApiCredential.
    META_APP_SECRET = os.getenv('META_APP_SECRET', '')
    META_WEBHOOK_VERIFY_TOKEN = os.getenv('META_WEBHOOK_VERIFY_TOKEN', '')
    META_GRAPH_API_BASE_URL = os.getenv('META_GRAPH_API_BASE_URL', 'https://graph.facebook.com')
    META_GRAPH_API_VERSION = os.getenv('META_GRAPH_API_VERSION', 'v23.0')

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
    # Auto-cadastro, quando excepcionalmente habilitado, vale só para esta
    # empresa. Nunca aceitar empresa_id enviado pelo navegador.
    SIGNUP_EMPRESA_ID = os.getenv('SIGNUP_EMPRESA_ID', '')

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

    # E-mail transacional via Resend (resend.com). Sem RESEND_API_KEY, o
    # email_service.py vira no-op com log de warning -- mesmo espirito do
    # Sentry sem DSN, seguro rodar local sem essa variavel configurada.
    RESEND_API_KEY = os.getenv('RESEND_API_KEY', '')
    # Precisa ser um remetente/dominio verificado na conta Resend.
    EMAIL_FROM = os.getenv('EMAIL_FROM', 'HUB <onboarding@resend.dev>')

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
