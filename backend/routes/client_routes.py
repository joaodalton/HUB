from flask import Blueprint, request

from services.client_service import (
    create_client,
    delete_client,
    get_client,
    list_clients,
    update_client
)
from utils.api_response import error_response, success_response


client_routes = Blueprint('client_routes', __name__, url_prefix='/clients')


@client_routes.route('', methods=['GET'])
def index():
    return success_response(list_clients())


@client_routes.route('/<int:client_id>', methods=['GET'])
def show(client_id: int):
    client = get_client(client_id)

    if not client:
        return error_response('Cliente nao encontrado.', 404)

    return success_response(client)


@client_routes.route('', methods=['POST'])
def store():
    data = request.get_json(silent=True) or {}

    if not data.get('nome', '').strip():
        return error_response('Nome e obrigatorio.', 400)
    if not data.get('cpf', '').strip():
        return error_response('CPF e obrigatorio.', 400)
    if not data.get('email', '').strip():
        return error_response('Email e obrigatorio.', 400)

    client = create_client(data)
    return success_response(client, 'Cliente cadastrado.', 201)


@client_routes.route('/<int:client_id>', methods=['PUT'])
def update(client_id: int):
    data = request.get_json(silent=True) or {}

    if not data.get('nome', '').strip():
        return error_response('Nome e obrigatorio.', 400)
    if not data.get('cpf', '').strip():
        return error_response('CPF e obrigatorio.', 400)
    if not data.get('email', '').strip():
        return error_response('Email e obrigatorio.', 400)

    client = update_client(client_id, data)

    if not client:
        return error_response('Cliente nao encontrado.', 404)

    return success_response(client, 'Cliente atualizado.')


@client_routes.route('/<int:client_id>', methods=['DELETE'])
def destroy(client_id: int):
    if not delete_client(client_id):
        return error_response('Cliente nao encontrado.', 404)

    return success_response(None, 'Cliente excluido.')