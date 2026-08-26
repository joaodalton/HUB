# backend/routes/fatura_routes.py
from flask import Blueprint, request

from config import Config
from services.fatura_service import cancelar_fatura, criar_fatura, get_fatura, list_faturas, processar_webhook
from services.log_service import LogService
from services.permission_service import require_permission
from utils.api_response import error_response, success_response


fatura_routes = Blueprint('fatura_routes', __name__, url_prefix='/api/v1/faturas')


@fatura_routes.route('', methods=['GET'])
@require_permission('rateios.read')
def index():
    filtros = {
        'clienteId': request.args.get('clienteId', type=int),
        'status': request.args.get('status'),
        'competencia': request.args.get('competencia')
    }
    return success_response(list_faturas(filtros))


@fatura_routes.route('/<int:fatura_id>', methods=['GET'])
@require_permission('rateios.read')
def show(fatura_id: int):
    fatura = get_fatura(fatura_id)
    if not fatura:
        return error_response('Fatura não encontrada.', 404)
    return success_response(fatura)


@fatura_routes.route('', methods=['POST'])
@require_permission('rateios.calculate')
def store():
    data = request.get_json(silent=True) or {}

    try:
        fatura = criar_fatura(data)
    except ValueError as exc:
        return error_response(str(exc), 400)

    return success_response(fatura, 'Fatura criada e cobrança gerada.', 201)


@fatura_routes.route('/<int:fatura_id>/cancelar', methods=['POST'])
@require_permission('rateios.calculate')
def cancel(fatura_id: int):
    try:
        fatura = cancelar_fatura(fatura_id)
    except ValueError as exc:
        return error_response(str(exc), 400)

    if not fatura:
        return error_response('Fatura não encontrada.', 404)

    return success_response(fatura, 'Fatura cancelada.')


# Rota PÚBLICA (sem token de sessão) -- chamada pelo próprio ASAAS quando o
# status de um pagamento muda. Validada pelo header 'asaas-access-token'
# (configurado no painel do ASAAS), não por cookie/Bearer.
@fatura_routes.route('/webhook/asaas', methods=['POST'])
def webhook_asaas():
    if Config.ASAAS_WEBHOOK_TOKEN:
        token_recebido = request.headers.get('asaas-access-token', '')
        if token_recebido != Config.ASAAS_WEBHOOK_TOKEN:
            return error_response('Token de webhook inválido.', 401)
    else:
        LogService.warning(
            acao='asaas_webhook_sem_validacao',
            mensagem='ASAAS_WEBHOOK_TOKEN não configurado -- webhook aceito sem validar origem.',
            entidade='Fatura'
        )

    payload = request.get_json(silent=True) or {}
    LogService.info(
        acao='asaas_webhook_recebido',
        mensagem='Webhook do ASAAS recebido.',
        entidade='Fatura',
        metadados={'payload': payload}
    )
    processar_webhook(payload)

    # ASAAS só espera 200 -- sempre responde OK, mesmo pra evento
    # desconhecido/ignorado (erro de verdade já foi logado dentro do service).
    return success_response(None, 'Webhook recebido.')
