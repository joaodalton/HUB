# backend/routes/auth_routes.py
from flask import Blueprint, g, jsonify, request

from extensions import limiter
from services.auth_service import authenticate
from services.invitation_service import aceitar_convite
from services.password_reset_service import redefinir_senha, solicitar_reset
from services.user_service import register_with_code
from utils.api_response import error_response, success_response
from utils.auth import clear_auth_cookies, set_auth_cookies


auth_routes = Blueprint('auth_routes', __name__, url_prefix='/api/v1/auth')


@auth_routes.route('/bootstrap', methods=['POST'])
def bootstrap():
    # Aposentada a partir do multi-tenant (2026-08-17): "primeiro usuario
    # de todo o banco" não faz mais sentido quando podem existir várias
    # empresas. Criar empresa + admin agora é manual, via
    # scripts/criar_empresa.py, direto no servidor -- decisão registrada em
    # VISAO.md secao 2.1 (self-signup público fica pra depois, se um dia
    # fizer sentido).
    return error_response(
        'Bootstrap publico desativado. Empresas sao criadas manualmente -- '
        'ver backend/scripts/criar_empresa.py.',
        403
    )


@auth_routes.route('/register', methods=['POST'])
@limiter.limit('5 per minute')
def register():
    # Desativado por decisão (2026-08-19): não existe mais auto-cadastro
    # público, viewer ou owner. O único caminho pra entrar no HUB é convite
    # (Invitation, aceitar-convite) -- pra empresa nova, o link de convite
    # do owner já cria empresa + conta juntos (ver scripts/criar_empresa.py).
    # Modelo futuro (planos pagos): o link de convite será enviado por
    # e-mail após a compra, continuando 100% por convite -- nunca um
    # formulário público com código.
    return error_response('Cadastro público desativado. Use o link de convite recebido por e-mail.', 403)

@auth_routes.route('/aceitar-convite', methods=['POST'])
@limiter.limit('10 per minute')
def aceitar_convite_route():
    data = request.get_json(silent=True) or {}
    token = data.get('token', '')
    nome = data.get('nome', '')
    senha = data.get('senha', '')

    if not token:
        return error_response('Token e obrigatorio.', 400)

    try:
        user = aceitar_convite(token, nome, senha)
    except ValueError as exc:
        return error_response(str(exc), 400)

    return success_response(user, 'Conta criada. Faca login.', 201)

@auth_routes.route('/login', methods=['POST'])
@limiter.limit('5 per minute')
def login():
    data = request.get_json(silent=True) or {}
    email = data.get('email', '').strip()
    senha = data.get('senha', '')

    if not email or not senha:
        return error_response('Email e senha sao obrigatorios.', 400)

    result = authenticate(email, senha)
    if not result:
        return error_response('Email ou senha invalidos.', 401)

    lembrar = bool(data.get('lembrar', False))

    response = jsonify({'success': True, 'message': 'Login realizado.', 'data': result['user']})
    set_auth_cookies(response, result['token'], remember=lembrar)
    return response


@auth_routes.route('/logout', methods=['POST'])
def logout():
    response = jsonify({'success': True, 'message': 'Logout realizado.', 'data': None})
    clear_auth_cookies(response)
    return response


@auth_routes.route('/me', methods=['GET'])
def me():
    user = g.current_user.to_dict()
    user['empresaNome'] = g.current_empresa.nome if g.current_empresa else None

    # So preenche pra platform admin -- usuario comum nunca tem esses campos.
    if g.current_user.is_platform_admin:
        viendo_empresa_id = getattr(g, 'platform_view_empresa_id', None)
        user['platformViewEmpresaId'] = viendo_empresa_id
        user['platformViewEmpresaNome'] = g.current_empresa.nome if viendo_empresa_id else None
        user['homeEmpresaId'] = g.current_user.empresa_id

    return success_response(user)

@auth_routes.route('/esqueci-senha', methods=['POST'])
@limiter.limit('5 per minute')
def esqueci_senha():
    data = request.get_json(silent=True) or {}
    solicitar_reset(data.get('email', ''))

    # Sempre a mesma mensagem, mesmo se o e-mail nao existir -- nao revela
    # pra quem pediu se aquele endereco tem conta cadastrada (ver
    # password_reset_service.solicitar_reset).
    return success_response(None, 'Se o e-mail existir em nossa base, você receberá um link de redefinição em instantes.')


@auth_routes.route('/redefinir-senha', methods=['POST'])
@limiter.limit('5 per minute')
def redefinir_senha_route():
    data = request.get_json(silent=True) or {}
    token = data.get('token', '')
    nova_senha = data.get('senha', '')

    if not token:
        return error_response('Token é obrigatório.', 400)

    try:
        redefinir_senha(token, nova_senha)
    except ValueError as exc:
        return error_response(str(exc), 400)

    return success_response(None, 'Senha redefinida com sucesso. Faça login com a nova senha.')
