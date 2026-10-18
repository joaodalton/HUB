# backend/routes/platform_worker_routes.py
"""
Gestao de contas platform_worker -- exclusivo de platform_admin
(require_platform_admin(), NAO require_platform_access(): um worker
nunca pode gerenciar outros workers).
"""
from flask import Blueprint, request

from services.permission_service import require_platform_admin
from services.platform_worker_service import create_platform_worker, list_platform_workers, revoke_platform_worker
from utils.api_response import error_response, success_response


platform_worker_routes = Blueprint('platform_worker_routes', __name__, url_prefix='/api/v1/platform/funcionarios')


@platform_worker_routes.route('', methods=['GET'])
@require_platform_admin()
def index():
    return success_response(list_platform_workers())


@platform_worker_routes.route('', methods=['POST'])
@require_platform_admin()
def store():
    data = request.get_json(silent=True) or {}

    try:
        worker = create_platform_worker(data)
    except ValueError as exc:
        return error_response(str(exc), 400)

    return success_response(worker, 'Funcionario criado.', 201)


@platform_worker_routes.route('/<int:user_id>', methods=['DELETE'])
@require_platform_admin()
def destroy(user_id: int):
    worker = revoke_platform_worker(user_id)
    if not worker:
        return error_response('Funcionario nao encontrado.', 404)
    return success_response(worker, 'Funcionario revogado.')
