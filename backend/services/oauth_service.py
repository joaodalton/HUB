# backend/services/oauth_service.py
"""
Fluxo OAuth 2.0 pra conectar conta(s) Google reais de usuario -- complementa
(nao substitui ainda) o credentials.json de service account usado hoje pelo
Drive. Nao inicializa nada em tempo de import, so quando authorize()/callback()
sao chamados (mesmo espirito lazy do drive_service.py).

Guarda em memoria o 'state' pendente entre /authorize e /callback como
protecao CSRF basica. Isso assume processo unico (waitress/dev server nao
multi-processo) -- se um dia o backend rodar com varios workers, precisa
mover pra algo compartilhado (Setting no banco, por exemplo).
"""
import os
import secrets

import requests as http_requests
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

from config import Config
from extensions import db
from models.google_account import GoogleAccount
from services.log_service import LogService

# oauthlib recusa qualquer OAuth fora de HTTPS por padrao. Nosso redirect_uri e
# http://localhost:8000/... de proposito (app local, sem certificado) -- isso nao
# abaixa seguranca de verdade, a troca do code pelo token com o Google continua
# sempre HTTPS por baixo. Flag oficial da propria lib pra esse cenario (apps locais/instalados).
os.environ.setdefault('OAUTHLIB_INSECURE_TRANSPORT', '1')

# Sempre pede o mesmo escopo de Drive que a service account usa (fonte unica
# de verdade em Config.GOOGLE_DRIVE_SCOPES), mais 'email' so pra identificar
# qual conta Google foi conectada -- HUB nunca le nome/foto, so o email.
_IDENTITY_SCOPES = ['openid', 'https://www.googleapis.com/auth/userinfo.email']

_pending_states: dict[str, str] = {}  # state -> code_verifier (PKCE)


def _scopes() -> list[str]:
    return [*Config.GOOGLE_DRIVE_SCOPES, *_IDENTITY_SCOPES]


def _client_config() -> dict:
    if not Config.GOOGLE_OAUTH_CLIENT_ID or not Config.GOOGLE_OAUTH_CLIENT_SECRET:
        raise RuntimeError(
            'GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET nao configurados no .env. '
            'Crie um Client ID tipo "Web application" no Google Cloud Console primeiro.'
        )

    return {
        'web': {
            'client_id': Config.GOOGLE_OAUTH_CLIENT_ID,
            'client_secret': Config.GOOGLE_OAUTH_CLIENT_SECRET,
            'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
            'token_uri': 'https://oauth2.googleapis.com/token',
            'redirect_uris': [Config.GOOGLE_OAUTH_REDIRECT_URI]
        }
    }


def _build_flow() -> Flow:
    return Flow.from_client_config(
        _client_config(),
        scopes=_scopes(),
        redirect_uri=Config.GOOGLE_OAUTH_REDIRECT_URI
    )


def build_authorize_url() -> str:
    flow = _build_flow()
    state = secrets.token_urlsafe(24)

    auth_url, _ = flow.authorization_url(
        access_type='offline',     # necessario pra ganhar refresh_token
        prompt='consent',          # forca a tela de consentimento sempre -- sem isso o Google
                                    # as vezes nao manda refresh_token de novo pra quem ja autorizou antes
        include_granted_scopes='true',
        state=state
    )

    # google-auth-oauthlib >=1.2 gera PKCE (code_verifier/code_challenge) sozinho.
    # Precisa guardar o code_verifier junto do state, senao o Flow novo do callback
    # nao tem como reproduzir o code_challenge e a troca do code por token falha.
    _pending_states[state] = flow.code_verifier
    return auth_url


def handle_callback(request_url: str, state: str) -> dict:
    """Troca o 'code' que o Google devolveu por credenciais, descobre o email
    da conta e cria/atualiza o GoogleAccount correspondente."""
    if state not in _pending_states:
        raise ValueError('Link de autorizacao invalido ou expirado. Conecte a conta de novo.')

    code_verifier = _pending_states.pop(state)

    flow = _build_flow()
    flow.code_verifier = code_verifier  # mesmo verifier do authorize -- exigido pelo PKCE
    flow.fetch_token(authorization_response=request_url)
    credentials = flow.credentials

    if not credentials.refresh_token:
        raise ValueError(
            'Google nao retornou refresh_token. Revogue o acesso do HUB em '
            'myaccount.google.com/permissions e tente conectar de novo.'
        )

    email = _fetch_email(credentials)
    account = GoogleAccount.query.filter_by(email=email).first()

    if not account:
        account = GoogleAccount(email=email, nome=email.split('@')[0])
        db.session.add(account)
        db.session.flush()

    account.nome = account.nome or email.split('@')[0]
    account.set_refresh_token(credentials.refresh_token)
    account.scopes = ','.join(credentials.scopes or _scopes())

    # primeira conta conectada vira ativa sozinha; as seguintes ficam inativas
    # ate o usuario escolher em Configuracoes.
    if not GoogleAccount.query.filter_by(is_active=True).first():
        account.is_active = True

    db.session.commit()
    _invalidate_drive_cache()

    LogService.info(
        acao='oauth_connect',
        mensagem=f'Conta Google {email} conectada via OAuth',
        entidade='GoogleAccount',
        metadados={'id': account.id}
    )
    return account.to_dict()


def _fetch_email(credentials: Credentials) -> str:
    response = http_requests.get(
        'https://www.googleapis.com/oauth2/v2/userinfo',
        headers={'Authorization': f'Bearer {credentials.token}'},
        timeout=10
    )
    response.raise_for_status()
    return response.json()['email']


def list_accounts() -> list[dict]:
    accounts = GoogleAccount.query.order_by(GoogleAccount.created_at.desc()).all()
    return [account.to_dict() for account in accounts]


def set_active_account(account_id: int) -> dict | None:
    account = GoogleAccount.query.get(account_id)
    if not account:
        return None

    GoogleAccount.query.update({GoogleAccount.is_active: False})
    account.is_active = True
    db.session.commit()
    _invalidate_drive_cache()

    LogService.info(acao='oauth_activate', mensagem=f'Conta Google {account.email} ativada', entidade='GoogleAccount', metadados={'id': account.id})
    return account.to_dict()


def disconnect_account(account_id: int) -> bool:
    account = GoogleAccount.query.get(account_id)
    if not account:
        return False

    email, was_active = account.email, account.is_active
    db.session.delete(account)
    db.session.commit()

    if was_active:
        _invalidate_drive_cache()

    LogService.info(acao='oauth_disconnect', mensagem=f'Conta Google {email} desconectada', entidade='GoogleAccount')
    return True


def _invalidate_drive_cache() -> None:
    # import tardio pra evitar ciclo de import (drive_service tambem pode vir
    # a importar coisas daqui no futuro).
    from services.drive_service import invalidate_drive_cache
    invalidate_drive_cache()