# backend/routes/user_routes.py
from flask import Blueprint, g, request

from services.permission_service import require_permission
from services.user_service import create_user, list_users, set_user_active, update_user
from utils.api_response import error_response, success_response


user_routes = Blueprint('user_routes', __name__, url_prefix='/api/v1/users')


@user_routes.route('', methods=['GET'])
@require_permission('users.read')
def index():
    return success_response(list_users(g.current_empresa_id))


@user_routes.route('', methods=['POST'])
@require_permission('users.create')
def store():
    data = request.get_json(silent=True) or {}

    try:
        user = create_user(data, g.current_empresa_id)
    except ValueError as exc:
        return error_response(str(exc), 409)

    return success_response(user, 'Usuario criado.', 201)


@user_routes.route('/<int:user_id>', methods=['PUT'])
@require_permission('users.update')
def update(user_id: int):
    try:
        user = update_user(user_id, request.get_json(silent=True) or {}, g.current_empresa_id)
    except ValueError as exc:
        return error_response(str(exc), 400)
    if not user:
        return error_response('Usuario nao encontrado.', 404)
    return success_response(user, 'Usuario atualizado.')


@user_routes.route('/<int:user_id>/ativo', methods=['PUT'])
@require_permission('users.deactivate', 'users.reactivate')
def update_active(user_id: int):
    data = request.get_json(silent=True) or {}
    ativo = data.get('ativo')
    if type(ativo) is not bool:
        return error_response('Campo ativo deve ser booleano.', 400)

    if user_id == g.current_user.id and not ativo:
        return error_response('Voce nao pode desativar sua propria conta.', 400)

    try:
        user = set_user_active(user_id, g.current_empresa_id, ativo)
    except ValueError as exc:
        return error_response(str(exc), 400)

    if not user:
        return error_response('Usuario nao encontrado.', 404)

    return success_response(user, 'Usuario atualizado.')
