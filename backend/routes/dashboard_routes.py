from flask import Blueprint

from services.dashboard_service import get_resumo_operacional
from services.permission_service import require_permission
from utils.api_response import success_response


dashboard_routes = Blueprint('dashboard_routes', __name__, url_prefix='/api/v1/dashboard')


@dashboard_routes.route('/resumo', methods=['GET'])
@require_permission('pendencias.read')
def resumo():
    """Resumo operacional derivado dos dados da empresa ativa."""
    return success_response(get_resumo_operacional())
