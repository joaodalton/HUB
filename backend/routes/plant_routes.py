# backend/routes/plant_routes.py
from flask import Blueprint, request

from services.plant_service import (
    create_plant,
    delete_plant,
    get_plant,
    list_plants,
    update_plant
)
from utils.api_response import error_response, success_response


plant_routes = Blueprint('plant_routes', __name__, url_prefix='/plants')


@plant_routes.route('', methods=['GET'])
def index():
    return success_response(list_plants())


@plant_routes.route('/<int:plant_id>', methods=['GET'])
def show(plant_id: int):
    plant = get_plant(plant_id)
    if not plant:
        return error_response('Usina nao encontrada.', 404)
    return success_response(plant)


@plant_routes.route('', methods=['POST'])
def store():
    data = request.get_json(silent=True) or {}
    if not data.get('nome', '').strip():
        return error_response('Nome e obrigatorio.', 400)
    return success_response(create_plant(data), 'Usina cadastrada.', 201)


@plant_routes.route('/<int:plant_id>', methods=['PUT'])
def update(plant_id: int):
    data = request.get_json(silent=True) or {}
    plant = update_plant(plant_id, data)
    if not plant:
        return error_response('Usina nao encontrada.', 404)
    return success_response(plant, 'Usina atualizada.')


@plant_routes.route('/<int:plant_id>', methods=['DELETE'])
def destroy(plant_id: int):
    if not delete_plant(plant_id):
        return error_response('Usina nao encontrada.', 404)
    return success_response(None, 'Usina excluida.')