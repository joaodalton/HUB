# backend/routes/oauth_routes.py
from urllib.parse import urlencode

from flask import Blueprint, g, redirect, request

from config import Config
from services.log_service import LogService
from services.permission_service import require_permission
from services.oauth_service import (
    build_authorize_url,
    _configure_transport_security,
    disconnect_account,
    handle_callback,
    list_accounts,
    set_active_account
)
from utils.api_response import error_response, success_response

oauth_routes = Blueprint('oauth_routes', __name__, url_prefix='/api/v1/oauth/google')


def _configured_callback_url(query_string: bytes) -> str:
    """Preserva query do Google, mas fixa scheme/host no callback registrado."""
    separador = '&' if '?' in Config.GOOGLE_OAUTH_REDIRECT_URI else '?'
    return f'{Config.GOOGLE_OAUTH_REDIRECT_URI}{separador}{query_string.decode("ascii")}'


def _frontend_oauth_redirect(resultado: str, motivo: str | None = None) -> str:
    parametros = {'google_oauth': resultado}
    if motivo:
        parametros['motivo'] = motivo
    destino = f'{Config.FRONTEND_URL.rstrip("/")}/configuracoes'
    separador = '&' if '?' in destino else '?'
    return f'{destino}{separador}{urlencode(parametros)}'


# GET /api/v1/oauth/google/authorize -- redireciona o navegador pra tela de consentimento do Google.
# Publica pro middleware (sem exigir token), mas resolve o usuario "na mao"
# aqui dentro -- precisa saber a empresa de quem clicou "Conectar nova
# conta" antes de mandar pro Google (ver resolve_current_user_optional).
@oauth_routes.route('/authorize')
@require_permission('settings.update')
def authorize():
    try:
        return redirect(build_authorize_url(g.current_empresa_id))
    except RuntimeError as exc:
        return error_response(str(exc), 503)


# GET /api/v1/oauth/google/callback -- o Google chama essa URL de volta com ?code=...&state=...
# Tambem publica pelo mesmo motivo da rota acima. Sempre volta pro frontend (nunca fica presa no backend).
@oauth_routes.route('/callback')
def callback():
    # Esta rota e publica e pode receber callback com erro antes de _build_flow
    # ser executado. Validar aqui garante que nenhum ramo redirecione para HTTP
    # publico ou para URL malformada.
    try:
        _configure_transport_security()
    except RuntimeError as exc:
        return error_response(str(exc), 503)

    if request.args.get('error'):
        return redirect(_frontend_oauth_redirect('erro', request.args['error']))

    try:
        # Em produção o URI registrado é HTTPS. Não usar request.url aqui:
        # atrás do proxy TLS do Render ele pode aparecer internamente como
        # HTTP, o que faria oauthlib rejeitar um callback público válido.
        handle_callback(_configured_callback_url(request.query_string), request.args.get('state', ''))
    except ValueError as exc:
        return redirect(_frontend_oauth_redirect('erro', str(exc)))
    except Exception as exc:
        LogService.error(
            acao='oauth_callback_failed',
            mensagem=f'Falha inesperada no callback OAuth: {exc}',
            entidade='GoogleAccount'
        )
        return redirect(_frontend_oauth_redirect('erro', str(exc)))

    return redirect(_frontend_oauth_redirect('sucesso'))


# GET /api/v1/oauth/google/accounts -- lista contas Google conectadas DA EMPRESA do usuario logado.
@oauth_routes.route('/accounts')
@require_permission('settings.read')
def accounts():
    return success_response(list_accounts(g.current_empresa_id))


# POST /api/v1/oauth/google/accounts/<id>/activate -- troca qual conta e a ativa (so uma por vez, por empresa).
@oauth_routes.route('/accounts/<int:account_id>/activate', methods=['POST'])
@require_permission('settings.update')
def activate(account_id: int):
    account = set_active_account(account_id, g.current_empresa_id)
    if not account:
        return error_response('Conta nao encontrada.', 404)
    return success_response(account, 'Conta ativada.')


# DELETE /api/v1/oauth/google/accounts/<id> -- desconecta e apaga a conta salva (nao revoga no lado do Google).
@oauth_routes.route('/accounts/<int:account_id>', methods=['DELETE'])
@require_permission('settings.update')
def destroy(account_id: int):
    if not disconnect_account(account_id, g.current_empresa_id):
        return error_response('Conta nao encontrada.', 404)
    return success_response(None, 'Conta desconectada.')
