"""Dashboard do financeiro: agregados por cliente e por usina."""
import re

from flask import Blueprint, g, request

from services.financeiro_service import obter_dashboard
from services.permission_service import require_permission
from utils.api_response import error_response, success_response

financeiro_routes = Blueprint('financeiro_routes', __name__, url_prefix='/api/v1/financeiro')

COMPETENCIA_RE = re.compile(r'^\d{4}-\d{2}$')


@financeiro_routes.get('/dashboard')
@require_permission('billing_calculations.read')
def dashboard():
    competencia = request.args.get('competencia')
    if competencia and not COMPETENCIA_RE.match(competencia):
        return error_response('Parâmetro competencia inválido, use o formato AAAA-MM.', 400)
    return success_response(obter_dashboard(g.current_empresa_id, competencia))
