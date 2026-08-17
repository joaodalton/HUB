# backend/routes/invitation_routes.py
from flask import Blueprint, g, request

from config import Config
from services.invitation_service import criar_convite, listar_convites, verificar_convite
from services.permission_service import require_permission
from utils.api_response import error_response, success_response


invitation_routes = Blueprint('invitation_routes', __name__, url_prefix='/api/v1/convites')


# GET /api/v1/convites -- lista os convites da empresa do usuario logado (autenticada).
@invitation_routes.route('', methods=['GET'])
@require_permission('invitations.read')
def index():
    return success_response(listar_convites(g.current_user.empresa_id))


# POST /api/v1/convites -- cria um convite novo (autenticada, so owner/admin).
@invitation_routes.route('', methods=['POST'])
@require_permission('invitations.create')
def store():
    data = request.get_json(silent=True) or {}
    email = data.get('email', '')
    role = data.get('role', '')

    if not email or not role:
        return error_response('Email e papel sao obrigatorios.', 400)

    try:
        convite, token = criar_convite(g.current_user.empresa_id, email, role, g.current_user.id)
    except ValueError as exc:
        return error_response(str(exc), 400)

    # Sem envio automatico de email/WhatsApp ainda -- o link vem pronto na
    # resposta pra quem convidou copiar e mandar na mao.
    convite['link'] = f'{Config.FRONTEND_URL}/aceitar-convite?token={token}'
    return success_response(convite, 'Convite criado.', 201)


# GET /api/v1/convites/verificar?token=... -- PUBLICA. Usada pela tela de aceite
# pra mostrar "voce foi convidado pra <empresa> como <papel>" antes do formulario.
@invitation_routes.route('/verificar', methods=['GET'])
def verificar():
    token = request.args.get('token', '')
    if not token:
        return error_response('Token e obrigatorio.', 400)

    try:
        info = verificar_convite(token)
    except ValueError as exc:
        return error_response(str(exc), 400)

    return success_response(info)