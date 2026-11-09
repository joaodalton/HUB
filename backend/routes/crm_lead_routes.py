from flask import Blueprint, g

from extensions import limiter
from services import crm_lead_service as service
from services.crm.piperun_client import PipeRunError
from services.permission_service import require_permission
from utils.api_response import error_response, success_response

crm_lead_routes = Blueprint('crm_lead_routes', __name__, url_prefix='/api/v1/crm-leads')


@crm_lead_routes.get('')
@require_permission('settings.read')
def index():
    return success_response(service.listar(g.current_empresa_id))


@crm_lead_routes.post('/sincronizar')
@limiter.limit('5 per minute')
@require_permission('settings.update')
def sync():
    try:
        resumo = service.sincronizar(g.current_empresa_id)
    except ValueError as exc:
        return error_response(str(exc), 400)
    except PipeRunError as exc:
        return error_response(str(exc), 503)
    return success_response(resumo, 'Sincronizacao com o PipeRun concluida.')
