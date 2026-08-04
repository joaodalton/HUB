# backend/routes/log_routes.py
from flask import Blueprint, request

from services.log_service import LogService
from utils.api_response import success_response


log_routes = Blueprint('log_routes', __name__, url_prefix='/api/v1/logs')


# GET /logs?limit=50&nivel=warning -- lista os logs mais recentes (mais novo primeiro).
# 'limit' tem teto de 200 pra nao deixar alguem pedir o log inteiro numa unica resposta.
@log_routes.route('', methods=['GET'])
def index():
    limit = min(request.args.get('limit', default=50, type=int) or 50, 200)
    nivel = request.args.get('nivel') or None

    return success_response(LogService.list_recent(limit=limit, nivel=nivel))