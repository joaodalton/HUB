# backend/routes/user_routes.py
"""
Rotas de usuários:
  GET    /api/v1/users                lista (platform admin ou dono da empresa)
  POST   /api/v1/users                cria usuário
  PUT    /api/v1/users/<int:id>       atualiza (nome, email, papel)
  PUT    /api/v1/users/<int:id>/ativo  ativa/desativa
  DELETE /api/v1/users/<int:id>       exclui
  POST   /api/v1/users/<int:id>/redefinir-senha  redefinição por conta própria
"""
from flask import Blueprint, g, request
from extensions import db
from models.user import User
from services.permission_service import require_permission
from services.user_service import (
    create_user,
    delete_user,
    list_users,
    set_user_active,
    update_user,
)
from utils.api_response import error_response, success_response
from utils.auth import hash_password
from services.log_service import LogService

user_routes = Blueprint("user_routes", __name__, url_prefix="/api/v1/users")


@user_routes.route("", methods=["GET"])
@require_permission("users.read")
def index():
    return success_response(list_users(g.current_user.empresa_id))


@user_routes.route("", methods=["POST"])
@require_permission("users.create")
def store():
    data = request.get_json(silent=True) or {}

    try:
        user = create_user(data, g.current_user.empresa_id, g.current_user.id)
    except ValueError as exc:
        return error_response(str(exc), 409)

    # Se o retorno tiver inviteCode, é um convite (usuário criado sem senha)
    if isinstance(user, dict) and "inviteCode" in user:
        return success_response(
            user,
            "Usuario convidado. Um email sera enviado para ele definir sua senha.",
            201,
        )

    return success_response(user, "Usuario criado.", 201)


@user_routes.route("/<int:user_id>", methods=["PUT"])
@require_permission("users.update")
def update(user_id: int):
    data = request.get_json(silent=True) or {}
    ativo = data.get("ativo")

    # desativação via campo ativo no body
    if ativo is not None:
        ativo_bool = bool(ativo)
        if user_id == g.current_user.id and not ativo_bool:
            return error_response("Voce nao pode desativar sua propria conta.", 400)
        try:
            user = set_user_active(user_id, g.current_user.empresa_id, ativo_bool)
        except ValueError as exc:
            return error_response(str(exc), 400)

        if not user:
            return error_response("Usuario nao encontrado.", 404)

        return success_response(user, "Usuario atualizado.")

    # atualiza nome, email, papel
    try:
        user = update_user(user_id, data, g.current_user.empresa_id)
    except ValueError as exc:
        return error_response(str(exc), 400)

    if not user:
        return error_response("Usuario nao encontrado.", 404)

    return success_response(user, "Usuario atualizado.")


@user_routes.route("/<int:user_id>", methods=["DELETE"])
@require_permission("users.delete")
def destroy(user_id: int):
    try:
        delete_user(user_id, g.current_user.empresa_id)
    except ValueError as exc:
        return error_response(str(exc), 400)

    return success_response(None, "Usuario excluido.", 200)


@user_routes.route("/<int:user_id>/ativo", methods=["PUT"])
@require_permission("users.update")
def toggle_active(user_id: int):
    data = request.get_json(silent=True) or {}
    ativo = bool(data.get("ativo", True))

    if user_id == g.current_user.id and not ativo:
        return error_response("Voce nao pode desativar sua propria conta.", 400)

    try:
        user = set_user_active(user_id, g.current_user.empresa_id, ativo)
    except ValueError as exc:
        return error_response(str(exc), 400)

    if not user:
        return error_response("Usuario nao encontrado.", 404)

    return success_response(user, "Usuario atualizado.")


@user_routes.route("/<int:user_id>/redefinir-senha", methods=["POST"])
def redefinir_senha(user_id: int):
    """
    Redefinição de senha: o próprio usuário OU um admin/platform admin
    pode redefinir a senha de qualquer usuário.
    """
    is_self = user_id == g.current_user.id
    is_admin = getattr(g.current_user, "is_platform_admin", False)

    if not is_self and not is_admin:
        return error_response("Voce so pode redefinir sua propria senha.", 403)

    data = request.get_json(silent=True) or {}
    nova_senha = (data.get("nova_senha") or "").strip()
    confirmacao = (data.get("confirmacao") or "").strip()

    if not nova_senha:
        return error_response("Nova senha é obrigatória.", 400)
    if len(nova_senha) < 6:
        return error_response("Nova senha precisa ter pelo menos 6 caracteres.", 400)
    if nova_senha != confirmacao:
        return error_response("As senhas nao coincidem.", 400)

    user = User.query.get(user_id)
    if not user:
        return error_response("Usuario nao encontrado.", 404)

    user.password_hash = hash_password(nova_senha)
    user.must_change_password = False
    db.session.commit()

    LogService.info(
        acao="password_reset",
        mensagem=f"Usuario {user.email} redefiniu sua propria senha" if is_self else f"Admin redefiniu senha de {user.email}",
        entidade="User",
        metadados={"userId": user.id},
    )

    return success_response(None, "Senha redefinida com sucesso.")
