# backend/services/oauth_service.py
"""
Fluxo OAuth 2.0 pra conectar conta(s) Google reais de usuario -- complementa
(nao substitui ainda) o credentials.json de service account usado hoje pelo
Drive. Nao inicializa nada em tempo de import, so quando authorize()/callback()
sao chamados (mesmo espirito lazy do drive_service.py).

O 'state' pendente entre /authorize e /callback (protecao CSRF basica do PKCE)
fica guardado na tabela Setting, nao em memoria -- com Gunicorn rodando mais de
um worker (processos separados, cada um com sua propria memoria), guardar em
dict em memoria fazia o state "sumir" sempre que /authorize e /callback caiam
em processos diferentes (bug real, ja aconteceu em producao). Setting resolve
isso porque todo worker le do mesmo Postgres.
"""
import datetime
import json
import os
import secrets
from urllib.parse import urlparse

import requests as http_requests
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

from config import Config
from extensions import db
from models.google_account import GoogleAccount
from models.setting import Setting
from services.log_service import LogService

# Sempre pede o mesmo escopo de Drive que a service account usa (fonte unica
# de verdade em Config.GOOGLE_DRIVE_SCOPES), mais 'email' so pra identificar
# qual conta Google foi conectada -- HUB nunca le nome/foto, so o email.
_IDENTITY_SCOPES = ['openid', 'https://www.googleapis.com/auth/userinfo.email']

# Prefixo pra distinguir essas chaves das de aparencia (themeColor, logoDataUrl)
# que ja vivem na mesma tabela Setting -- sem colisao de namespace.
_STATE_KEY_PREFIX = 'oauth_pending_state:'
_STATE_TTL_MINUTES = 15  # state abandonado (usuario fechou a aba no meio) expira sozinho
_LOCAL_OAUTH_HOSTS = frozenset({'localhost', '127.0.0.1', '::1'})


def _scopes() -> list[str]:
    return [*Config.GOOGLE_DRIVE_SCOPES, *_IDENTITY_SCOPES]


def _store_pending_state(state: str, code_verifier: str, empresa_id: int) -> None:
    _cleanup_expired_states()
    # Guarda code_verifier (PKCE) E a empresa que iniciou o fluxo juntos --
    # o /callback e chamado direto pelo Google, sem sessao/cookie util pra
    # saber isso, entao precisa vir carregado dentro do proprio state.
    valor = json.dumps({'codeVerifier': code_verifier, 'empresaId': empresa_id})
    db.session.add(Setting(empresa_id=empresa_id, chave=f'{_STATE_KEY_PREFIX}{state}', valor=valor))
    db.session.commit()


def _pop_pending_state(state: str) -> dict | None:
    """Le e ja apaga -- state e de uso unico, senao um mesmo link de callback
    poderia ser reaproveitado. Retorna {'codeVerifier': ..., 'empresaId': ...}."""
    setting = Setting.query.filter_by(chave=f'{_STATE_KEY_PREFIX}{state}').first()
    if not setting:
        return None

    try:
        dados = json.loads(setting.valor)
    except (TypeError, ValueError):
        dados = None

    db.session.delete(setting)
    db.session.commit()
    return dados


def _cleanup_expired_states() -> None:
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(minutes=_STATE_TTL_MINUTES)
    Setting.query.filter(
        Setting.chave.like(f'{_STATE_KEY_PREFIX}%'),
        Setting.created_at < cutoff
    ).delete(synchronize_session=False)
    db.session.commit()


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


def _configure_transport_security() -> None:
    """Configura a excecao HTTP do OAuthlib apenas no localhost em dev.

    A variavel e global ao processo porque a propria oauthlib le o ambiente.
    Por isso ela tambem e removida explicitamente em qualquer configuracao de
    producao, inclusive se o host a tiver herdado por engano.
    """
    redirect = urlparse(Config.GOOGLE_OAUTH_REDIRECT_URI)
    frontend = urlparse(Config.FRONTEND_URL)
    is_explicit_local_dev = (
        Config.DEBUG
        and Config.OAUTH_ALLOW_INSECURE_TRANSPORT
        and redirect.scheme == 'http'
        and redirect.hostname in _LOCAL_OAUTH_HOSTS
    )
    if is_explicit_local_dev:
        _validate_frontend_url(frontend, allow_http_loopback=True)
        os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
        return

    os.environ.pop('OAUTHLIB_INSECURE_TRANSPORT', None)
    if not _is_absolute_https(redirect):
        raise RuntimeError(
            'GOOGLE_OAUTH_REDIRECT_URI deve usar HTTPS fora do desenvolvimento local explicito.'
        )
    _validate_frontend_url(frontend, allow_http_loopback=False)


def _is_absolute_https(parsed) -> bool:
    return (
        parsed.scheme == 'https'
        and bool(parsed.hostname)
        and not parsed.username
        and not parsed.password
        and not parsed.fragment
    )


def _validate_frontend_url(parsed, *, allow_http_loopback: bool) -> None:
    """Evita redirecionamento OAuth para URL relativa, HTTP público ou URL com credenciais."""
    local_http = (
        allow_http_loopback
        and parsed.scheme == 'http'
        and parsed.hostname in _LOCAL_OAUTH_HOSTS
        and not parsed.username
        and not parsed.password
        and not parsed.fragment
    )
    if local_http or _is_absolute_https(parsed):
        return
    raise RuntimeError(
        'FRONTEND_URL deve ser uma URL HTTPS absoluta sem credenciais ou fragmento fora do desenvolvimento local.'
    )


def _build_flow() -> Flow:
    _configure_transport_security()
    return Flow.from_client_config(
        _client_config(),
        scopes=_scopes(),
        redirect_uri=Config.GOOGLE_OAUTH_REDIRECT_URI
    )


def build_authorize_url(empresa_id: int) -> str:
    flow = _build_flow()
    state = secrets.token_urlsafe(24)

    auth_url, _ = flow.authorization_url(
        access_type='offline',     # necessario pra ganhar refresh_token
        prompt='consent',          # forca a tela de consentimento sempre -- sem isso o Google
                                    # as vezes nao manda refresh_token de novo pra quem ja autorizou antes
        state=state
    )

    # google-auth-oauthlib >=1.2 gera PKCE (code_verifier/code_challenge) sozinho.
    # Precisa guardar o code_verifier junto do state, senao o Flow novo do callback
    # nao tem como reproduzir o code_challenge e a troca do code por token falha.
    # empresa_id viaja junto pelo mesmo motivo -- ver _store_pending_state.
    _store_pending_state(state, flow.code_verifier, empresa_id)
    return auth_url


def handle_callback(request_url: str, state: str) -> dict:
    """Troca o 'code' que o Google devolveu por credenciais, descobre o email
    da conta e cria/atualiza o GoogleAccount correspondente -- SEMPRE dentro
    da empresa que iniciou o fluxo (empresa_id vindo do state, nao de
    g.current_empresa_id -- essa rota e publica, esse valor nao existe aqui)."""
    dados_state = _pop_pending_state(state)

    if dados_state is None:
        raise ValueError('Link de autorizacao invalido ou expirado. Conecte a conta de novo.')

    code_verifier = dados_state.get('codeVerifier')
    empresa_id = dados_state.get('empresaId')

    if not code_verifier or not empresa_id:
        raise ValueError('Link de autorizacao invalido ou expirado. Conecte a conta de novo.')

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
    # Filtro explicito por empresa_id (nao So confiar no TenantMixin aqui --
    # essa funcao roda fora de request autenticada, g.current_empresa_id
    # nao existe nesse ponto).
    account = GoogleAccount.query.filter_by(email=email, empresa_id=empresa_id).first()

    if not account:
        account = GoogleAccount(email=email, nome=email.split('@')[0], empresa_id=empresa_id)
        db.session.add(account)
        db.session.flush()

    account.nome = account.nome or email.split('@')[0]
    account.set_refresh_token(credentials.refresh_token)
    account.scopes = ','.join(credentials.scopes or _scopes())

    # primeira conta conectada DESSA EMPRESA vira ativa sozinha; as seguintes
    # ficam inativas ate o usuario escolher em Configuracoes.
    if not GoogleAccount.query.filter_by(is_active=True, empresa_id=empresa_id).first():
        account.is_active = True

    db.session.commit()
    _invalidate_drive_cache(empresa_id)

    LogService.info(
        acao='oauth_connect',
        mensagem=f'Conta Google {email} conectada via OAuth',
        entidade='GoogleAccount',
        metadados={'id': account.id, 'empresaId': empresa_id}
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


def list_accounts(empresa_id: int) -> list[dict]:
    accounts = GoogleAccount.query.filter_by(empresa_id=empresa_id).order_by(GoogleAccount.created_at.desc()).all()
    return [account.to_dict() for account in accounts]


def set_active_account(account_id: int, empresa_id: int) -> dict | None:
    account = GoogleAccount.query.filter_by(id=account_id, empresa_id=empresa_id).first()
    if not account:
        return None

    # Filtro explicito por empresa_id aqui tambem (nao so no .get) -- e um
    # UPDATE em massa, ponto sensivel o suficiente pra nao depender so do
    # filtro automatico do TenantMixin.
    GoogleAccount.query.filter_by(empresa_id=empresa_id).update({GoogleAccount.is_active: False})
    account.is_active = True
    db.session.commit()
    _invalidate_drive_cache(empresa_id)

    LogService.info(acao='oauth_activate', mensagem=f'Conta Google {account.email} ativada', entidade='GoogleAccount', metadados={'id': account.id})
    return account.to_dict()


def disconnect_account(account_id: int, empresa_id: int) -> bool:
    account = GoogleAccount.query.filter_by(id=account_id, empresa_id=empresa_id).first()
    if not account:
        return False

    email, was_active = account.email, account.is_active
    db.session.delete(account)
    db.session.commit()

    if was_active:
        _invalidate_drive_cache(empresa_id)

    LogService.info(acao='oauth_disconnect', mensagem=f'Conta Google {email} desconectada', entidade='GoogleAccount')
    return True


def _invalidate_drive_cache(empresa_id: int) -> None:
    # import tardio pra evitar ciclo de import (drive_service tambem pode vir
    # a importar coisas daqui no futuro).
    from services.drive_service import invalidate_drive_cache
    invalidate_drive_cache(empresa_id)
