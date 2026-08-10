# backend/routes/auth_routes.py
from flask import Blueprint, g, jsonify, request

from extensions import limiter
from models.user import User
from services.auth_service import authenticate, create_first_admin
from services.user_service import register_with_code
from utils.api_response import error_response, success_response
from utils.auth import clear_auth_cookies, set_auth_cookies


auth_routes = Blueprint('auth_routes', __name__, url_prefix='/api/v1/auth')


@auth_routes.route('/bootstrap', methods=['POST'])
def bootstrap():
    if User.query.count() > 0:
        return error_response('Bootstrap ja foi usado. Faca login em /api/v1/auth/login.', 403)

    data = request.get_json(silent=True) or {}
    email = data.get('email', '').strip()
    senha = data.get('senha', '')

    if not email or not senha:
        return error_response('Email e senha sao obrigatorios.', 400)
    if len(senha) < 6:
        return error_response('Senha precisa ter pelo menos 6 caracteres.', 400)

    user = create_first_admin(email, senha)
    return success_response(user.to_dict(), 'Usuario admin criado. Faca login em /api/v1/auth/login.', 201)


@auth_routes.route('/register', methods=['POST'])
@limiter.limit('5 per minute')
def register():
    data = request.get_json(silent=True) or {}
    codigo = (data.get('codigo') or '').strip()

    try:
        user = register_with_code(data, codigo)
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

    response = jsonify({'success': True, 'message': 'Login realizado.', 'data': result['user']})
    set_auth_cookies(response, result['token'])
    return response


@auth_routes.route('/logout', methods=['POST'])
def logout():
    response = jsonify({'success': True, 'message': 'Logout realizado.', 'data': None})
    clear_auth_cookies(response)
    return response


@auth_routes.route('/me', methods=['GET'])
def me():
    return success_response(g.current_user.to_dict())