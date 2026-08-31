from flask import Blueprint, request

from services.agenda_service import listar_itens
from services.permission_service import require_permission
from utils.api_response import error_response, success_response


agenda_routes = Blueprint('agenda_routes', __name__, url_prefix='/api/v1/agenda')


@agenda_routes.route('', methods=['GET'])
@require_permission('pendencias.read')
def index():
    """Prazos derivados de Pendencia na empresa autenticada, sem persistencia."""
    try:
        resultado = listar_itens(
            inicio=request.args.get('inicio'),
            fim=request.args.get('fim'),
            visao=request.args.get('visao'),
        )
    except ValueError as exc:
        return error_response(str(exc), 400)
    return success_response(resultado)
