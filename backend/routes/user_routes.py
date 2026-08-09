# backend/routes/user_routes.py
from flask import Blueprint, g, request

from services.user_service import create_user, list_users, set_user_active
from utils.api_response import error_response, success_response


user_routes = Blueprint('user_routes', __name__, url_prefix='/api/v1/users')


def _require_admin():
    if g.current_user.papel != 'admin':
        return error_response('So administradores podem gerenciar usuarios.', 403)
    return None


@user_routes.route('', methods=['GET'])
def index():
    denied = _require_admin()
    if denied:
        return denied
    return success_response(list_users())


@user_routes.route('', methods=['POST'])
def store():
    denied = _require_admin()
    if denied:
        return denied

    data = request.get_json(silent=True) or {}

    try:
        user = create_user(data)
    except ValueError as exc:
        return error_response(str(exc), 409)

    return success_response(user, 'Usuario criado.', 201)


@user_routes.route('/<int:user_id>/ativo', methods=['PUT'])
def update_active(user_id: int):
    denied = _require_admin()
    if denied:
        return denied

    data = request.get_json(silent=True) or {}
    ativo = bool(data.get('ativo', True))

    if user_id == g.current_user.id and not ativo:
        return error_response('Voce nao pode desativar sua propria conta.', 400)

    user = set_user_active(user_id, ativo)
    if not user:
        return error_response('Usuario nao encontrado.', 404)

    return success_response(user, 'Usuario atualizado.')