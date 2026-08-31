# backend/routes/log_routes.py
from flask import Blueprint, request

from services.log_service import LogService
from services.permission_service import require_permission
from utils.api_response import success_response


log_routes = Blueprint('log_routes', __name__, url_prefix='/api/v1/logs')


@log_routes.route('', methods=['GET'])
@require_permission('settings.read')
def index():
    limit = min(request.args.get('limit', default=50, type=int) or 50, 200)
    nivel = request.args.get('nivel') or None
    entidade = request.args.get('entidade') or None
    entidade_id = request.args.get('entidadeId', type=int)

    return success_response(LogService.list_recent(limit=limit, nivel=nivel, entidade=entidade, entidade_id=entidade_id))
