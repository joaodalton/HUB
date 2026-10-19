from flask import Blueprint, g, request

from services.asaas_client import AsaasError
from services.asaas_webhook_service import WebhookError, processar_webhook
from services.platform_asaas_webhook_service import receive_platform_webhook
from services.fatura_service import EmissaoPendente, cancelar, emitir, listar, obter, resumo, sincronizar
from services.permission_service import require_permission
from utils.api_response import error_response, success_response

fatura_routes = Blueprint('fatura_routes', __name__, url_prefix='/api/v1/faturas')


@fatura_routes.route('', methods=['GET'])
@require_permission('faturas.read')
def index():
    return success_response(listar(g.current_empresa_id, request.args))


@fatura_routes.route('', methods=['POST'])
@require_permission('faturas.create')
def store():
    try:
        return success_response(emitir(request.get_json(silent=True) or {}, g.current_empresa_id, g.current_user.id), 'Fatura processada.', 201)
    except PermissionError as exc:
        return error_response(str(exc), 403)
    except EmissaoPendente as exc:
        return error_response(str(exc), 409, code='EMISSAO_PENDENTE', details={'faturaId': exc.fatura_id})
    except (ValueError, AsaasError) as exc:
        return error_response(str(exc), 400)


@fatura_routes.route('/resumo', methods=['GET'])
@require_permission('faturas.read')
def get_resumo():
    return success_response(resumo(g.current_empresa_id))


@fatura_routes.route('/<int:fatura_id>', methods=['GET'])
@require_permission('faturas.read')
def detail(fatura_id: int):
    fatura = obter(fatura_id, g.current_empresa_id)
    return success_response(fatura.to_dict()) if fatura else error_response('Fatura não encontrada.', 404)


@fatura_routes.route('/<int:fatura_id>/sincronizar', methods=['POST'])
@require_permission('faturas.create')
def sync(fatura_id: int):
    fatura = obter(fatura_id, g.current_empresa_id)
    if not fatura: return error_response('Fatura não encontrada.', 404)
    try: return success_response(sincronizar(fatura))
    except EmissaoPendente as exc: return error_response(str(exc), 409, code='EMISSAO_PENDENTE', details={'faturaId': exc.fatura_id})
    except AsaasError as exc: return error_response(str(exc), 503)


@fatura_routes.route('/<int:fatura_id>/cancelar', methods=['POST'])
@require_permission('faturas.create')
def cancel(fatura_id: int):
    fatura = obter(fatura_id, g.current_empresa_id)
    if not fatura: return error_response('Fatura não encontrada.', 404)
    try: return success_response(cancelar(fatura), 'Fatura cancelada.')
    except EmissaoPendente as exc: return error_response(str(exc), 409, code='EMISSAO_PENDENTE', details={'faturaId': exc.fatura_id})
    except AsaasError as exc: return error_response(str(exc), 503)


webhook_routes = Blueprint('webhook_routes', __name__, url_prefix='/api/v1/webhooks')


@webhook_routes.route('/asaas', methods=['POST'])
def asaas_webhook():
    try:
        processar_webhook(request.get_json(silent=True), request.headers.get('asaas-access-token', ''))
    except WebhookError as exc:
        return error_response(str(exc), exc.status)
    return success_response({'received': True})


@webhook_routes.route('/asaas/platform', methods=['POST'])
def platform_asaas_webhook():
    try:
        receive_platform_webhook(request.get_json(silent=True), request.headers.get('asaas-access-token', ''))
    except WebhookError as exc:
        return error_response(str(exc), exc.status)
    return success_response({'received': True})
