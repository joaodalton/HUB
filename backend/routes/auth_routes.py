# backend/routes/auth_routes.py
from flask import Blueprint, g, jsonify, request

from extensions import limiter
from services.auth_service import authenticate
from services.invitation_service import aceitar_convite
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
    data = request.get_json(silent=True) or {}
    codigo = (data.get('codigo') or '').strip()

    # O tenant nunca vem do cliente: um SIGNUP_CODE global não pode dar
    # acesso a empresas cujo id foi apenas adivinhado. Para o fluxo normal,
    # use convite; esse endpoint só existe para um tenant explicitamente
    # configurado no servidor.
    try:
        empresa_id = int(Config.SIGNUP_EMPRESA_ID)
    except (TypeError, ValueError):
        return error_response('Cadastro público desativado. Use um convite da sua empresa.', 403)

    from models.empresa import Empresa
    if not Empresa.query.get(empresa_id):
        return error_response('Cadastro público indisponível: empresa configurada não existe.', 503)

    try:
        user = register_with_code(data, codigo, empresa_id)
    except ValueError as exc:
        return error_response(str(exc), 400)

    return success_response(user, 'Conta criada. Faca login.', 201)

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
    return success_response(user)
