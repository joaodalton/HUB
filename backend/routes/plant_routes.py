# backend/routes/plant_routes.py
from flask import Blueprint, request

from extensions import limiter
from services.plant_service import (
    create_plant,
    delete_plant,
    get_plant,
    list_plants,
    update_plant
)
from services.uc_service import remove_connection
from services.permission_service import require_permission, require_quota
from utils.api_response import error_response, success_response
from utils.pagination import get_pagination_params


plant_routes = Blueprint('plant_routes', __name__, url_prefix='/api/v1/plants')


@plant_routes.route('', methods=['GET'])
@require_permission('plants.read')
def index():
    page, page_size = get_pagination_params()
    plants, pagination = list_plants(page=page, page_size=page_size)
    return success_response(plants, pagination=pagination)


@plant_routes.route('/<int:plant_id>', methods=['GET'])
@require_permission('plants.read')
def show(plant_id: int):
    plant = get_plant(plant_id)
    if not plant:
        return error_response('Usina nao encontrada.', 404)
    return success_response(plant)


@plant_routes.route('', methods=['POST'])
@limiter.limit('30 per minute')
@require_permission('plants.create')
@require_quota('usinas')
def store():
    data = request.get_json(silent=True) or {}
    if not data.get('nome', '').strip():
        return error_response('Nome e obrigatorio.', 400)
    try:
        plant = create_plant(data)
    except ValueError as exc:
        return error_response(str(exc), 400)
    return success_response(plant, 'Usina cadastrada.', 201)


@plant_routes.route('/<int:plant_id>', methods=['PUT'])
@limiter.limit('30 per minute')
@require_permission('plants.update')
def update(plant_id: int):
    data = request.get_json(silent=True) or {}
    try:
        plant = update_plant(plant_id, data)
    except ValueError as exc:
        return error_response(str(exc), 400)
    if not plant:
        return error_response('Usina nao encontrada.', 404)
    return success_response(plant, 'Usina atualizada.')


@plant_routes.route('/<int:plant_id>', methods=['DELETE'])
@limiter.limit('30 per minute')
@require_permission('plants.delete')
def destroy(plant_id: int):
    if not delete_plant(plant_id):
        return error_response('Usina nao encontrada.', 404)
    return success_response(None, 'Usina excluida.')


@plant_routes.route('/<int:plant_id>/connections/<int:connection_id>', methods=['DELETE'])
@limiter.limit('30 per minute')
@require_permission('plants.update')
def destroy_connection(plant_id: int, connection_id: int):
    if not remove_connection(plant_id, connection_id):
        return error_response('Conexao nao encontrada.', 404)
    return success_response(None, 'UC desconectada da usina.')
