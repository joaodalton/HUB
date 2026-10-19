"""Dashboard do financeiro: agregados por cliente e por usina."""
from flask import Blueprint, g, request

from services.financeiro_service import obter_dashboard
from services.permission_service import require_permission
from utils.api_response import success_response

financeiro_routes = Blueprint('financeiro_routes', __name__, url_prefix='/api/v1/financeiro')


@financeiro_routes.get('/dashboard')
@require_permission('billing_calculations.read')
def dashboard():
    return success_response(obter_dashboard(g.current_empresa_id, request.args.get('competencia')))
