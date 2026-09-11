from flask import Blueprint, request

from extensions import limiter
from services.agenda_service import atualizar_evento, cancelar_evento, criar_evento, listar_itens
from services.permission_service import require_permission
from utils.api_response import error_response, success_response


agenda_routes = Blueprint('agenda_routes', __name__, url_prefix='/api/v1/agenda')


@agenda_routes.route('', methods=['GET'])
@require_permission('pendencias.read')
def index():
    """Pendências derivadas e eventos próprios da empresa autenticada."""
    try:
        resultado = listar_itens(
            inicio=request.args.get('inicio'),
            fim=request.args.get('fim'),
            visao=request.args.get('visao'),
        )
    except ValueError as exc:
        return error_response(str(exc), 400)
    return success_response(resultado)


@agenda_routes.route('/eventos', methods=['POST'])
@limiter.limit('30 per minute')
@require_permission('pendencias.create')
def store_event():
    try:
        return success_response(criar_evento(request.get_json(silent=True) or {}), 'Evento criado.', 201)
    except ValueError as exc:
        return error_response(str(exc), 400)


@agenda_routes.route('/eventos/<int:event_id>', methods=['PUT'])
@limiter.limit('30 per minute')
@require_permission('pendencias.update')
def update_event(event_id: int):
    try:
        event = atualizar_evento(event_id, request.get_json(silent=True) or {})
    except ValueError as exc:
        return error_response(str(exc), 400)
    return success_response(event, 'Evento atualizado.') if event else error_response('Evento nao encontrado.', 404)


@agenda_routes.route('/eventos/<int:event_id>', methods=['DELETE'])
@limiter.limit('30 per minute')
@require_permission('pendencias.delete')
def destroy_event(event_id: int):
    return success_response(None, 'Evento cancelado.') if cancelar_evento(event_id) else error_response('Evento nao encontrado.', 404)
