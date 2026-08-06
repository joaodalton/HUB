# backend/routes/oauth_routes.py
from flask import Blueprint, redirect, request

from config import Config
from services.log_service import LogService
from services.oauth_service import (
    build_authorize_url,
    disconnect_account,
    handle_callback,
    list_accounts,
    set_active_account
)
from utils.api_response import error_response, success_response

oauth_routes = Blueprint('oauth_routes', __name__, url_prefix='/api/v1/oauth/google')


# GET /api/v1/oauth/google/authorize -- redireciona o navegador pra tela de consentimento do Google.
# Publica (sem Bearer token) de proposito: e navegacao direta do navegador (<a href>), nao fetch com header.
@oauth_routes.route('/authorize')
def authorize():
    try:
        return redirect(build_authorize_url())
    except RuntimeError as exc:
        return error_response(str(exc), 503)


# GET /api/v1/oauth/google/callback -- o Google chama essa URL de volta com ?code=...&state=...
# Tambem publica pelo mesmo motivo da rota acima. Sempre volta pro frontend (nunca fica presa no backend).
@oauth_routes.route('/callback')
def callback():
    if request.args.get('error'):
        return redirect(f'{Config.FRONTEND_URL}/configuracoes?google_oauth=erro&motivo={request.args["error"]}')

    try:
        handle_callback(request.url, request.args.get('state', ''))
    except ValueError as exc:
        return redirect(f'{Config.FRONTEND_URL}/configuracoes?google_oauth=erro&motivo={exc}')
    except Exception as exc:
        LogService.error(
            acao='oauth_callback_failed',
            mensagem=f'Falha inesperada no callback OAuth: {exc}',
            entidade='GoogleAccount'
        )
        return redirect(f'{Config.FRONTEND_URL}/configuracoes?google_oauth=erro&motivo={exc}')

    return redirect(f'{Config.FRONTEND_URL}/configuracoes?google_oauth=sucesso')


# GET /api/v1/oauth/google/accounts -- lista contas Google conectadas. Rota autenticada normal (fetch do front).
@oauth_routes.route('/accounts')
def accounts():
    return success_response(list_accounts())


# POST /api/v1/oauth/google/accounts/<id>/activate -- troca qual conta e a ativa (so uma por vez).
@oauth_routes.route('/accounts/<int:account_id>/activate', methods=['POST'])
def activate(account_id: int):
    account = set_active_account(account_id)
    if not account:
        return error_response('Conta nao encontrada.', 404)
    return success_response(account, 'Conta ativada.')


# DELETE /api/v1/oauth/google/accounts/<id> -- desconecta e apaga a conta salva (nao revoga no lado do Google).
@oauth_routes.route('/accounts/<int:account_id>', methods=['DELETE'])
def destroy(account_id: int):
    if not disconnect_account(account_id):
        return error_response('Conta nao encontrada.', 404)
    return success_response(None, 'Conta desconectada.')