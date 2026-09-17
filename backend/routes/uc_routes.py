# backend/routes/uc_routes.py
from flask import Blueprint, request

from services.uc_service import create_uc, delete_uc, get_concessionaria_password, get_uc, list_ucs, update_uc
from services.permission_service import require_permission, require_quota, require_role
from utils.api_response import error_response, success_response


uc_routes = Blueprint('uc_routes', __name__, url_prefix='/api/v1/ucs')


@uc_routes.route('', methods=['GET'])
@require_permission('consumer_units.read')
def index():
    return success_response(list_ucs())


@uc_routes.route('/<int:uc_id>', methods=['GET'])
@require_permission('consumer_units.read')
def show(uc_id: int):
    uc = get_uc(uc_id)

    if not uc:
        return error_response('UC nao encontrada.', 404)

    return success_response(uc)


@uc_routes.route('/<int:uc_id>/senha-concessionaria', methods=['GET'])
@require_role('owner', 'admin')
def reveal_concessionaria_password(uc_id: int):
    try:
        result = get_concessionaria_password(uc_id)
    except RuntimeError:
        return error_response('Servico de criptografia indisponivel. Tente novamente mais tarde.', 503)

    if result is None:
        return error_response('UC nao encontrada.', 404)
    if not result:
        return error_response('Senha da concessionaria nao cadastrada para esta UC.', 404)
    return success_response(result)


@uc_routes.route('', methods=['POST'])
@require_permission('consumer_units.create')
@require_quota('ucs')
def store():
    data = request.get_json(silent=True) or {}

    if not data.get('clienteId'):
        return error_response('Cliente e obrigatorio.', 400)
    if not data.get('codigo', '').strip():
        return error_response('Codigo da UC e obrigatorio.', 400)

    try:
        uc = create_uc(data)
    except ValueError as exc:
        return error_response(str(exc), 409)

    return success_response(uc, 'UC cadastrada.', 201)


@uc_routes.route('/<int:uc_id>', methods=['PUT'])
@require_permission('consumer_units.update')
def update(uc_id: int):
    data = request.get_json(silent=True) or {}

    try:
        uc = update_uc(uc_id, data)
    except ValueError as exc:
        return error_response(str(exc), 409)

    if not uc:
        return error_response('UC nao encontrada.', 404)

    return success_response(uc, 'UC atualizada.')


@uc_routes.route('/<int:uc_id>', methods=['DELETE'])
@require_permission('consumer_units.delete')
def destroy(uc_id: int):
    if not delete_uc(uc_id):
        return error_response('UC nao encontrada.', 404)

    return success_response(None, 'UC excluida.')
