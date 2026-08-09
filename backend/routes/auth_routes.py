# backend/routes/auth_routes.py
from flask import Blueprint, g, jsonify, request

from extensions import limiter
from models.user import User
from services.auth_service import authenticate, create_first_admin
from utils.api_response import error_response, success_response
from utils.auth import clear_auth_cookies, set_auth_cookies


auth_routes = Blueprint('auth_routes', __name__, url_prefix='/api/v1/auth')


@auth_routes.route('/bootstrap', methods=['POST'])
def bootstrap():
    # So funciona uma vez -- depois que existir 1 usuario, essa rota sempre nega.
    # Fica publica de proposito (nao precisa de token pra criar o primeiro admin),
    # e isso e seguro porque ela se tranca sozinha depois do primeiro uso.
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


@auth_routes.route('/login', methods=['POST'])
@limiter.limit('5 per minute')  # freia forca bruta -- 5 tentativas por IP por minuto
def login():
    data = request.get_json(silent=True) or {}
    email = data.get('email', '').strip()
    senha = data.get('senha', '')

    if not email or not senha:
        return error_response('Email e senha sao obrigatorios.', 400)

    result = authenticate(email, senha)

    if not result:
        return error_response('Email ou senha invalidos.', 401)

    # Construido na mao (nao com success_response) porque precisamos do objeto
    # Response de verdade pra anexar os cookies antes de devolver. O token NAO
    # vai mais no corpo da resposta -- so no cookie HttpOnly, que o JavaScript
    # nunca consegue ler (nem com um XSS ativo). O front so recebe o usuario.
    response = jsonify({'success': True, 'message': 'Login realizado.', 'data': result['user']})
    set_auth_cookies(response, result['token'])
    return response


@auth_routes.route('/logout', methods=['POST'])
def logout():
    # Publica de proposito -- mesmo com cookie expirado/invalido, o usuario
    # ainda precisa conseguir "limpar" o navegador dele.
    response = jsonify({'success': True, 'message': 'Logout realizado.', 'data': None})
    clear_auth_cookies(response)
    return response


@auth_routes.route('/me', methods=['GET'])
def me():
    # Rota protegida normal (passa pelo middleware) -- e como o frontend
    # descobre se o cookie que o navegador tem ainda e valido, ja que ele
    # nao consegue mais ler o token sozinho (proposital, e o cookie sendo
    # HttpOnly).
    return success_response(g.current_user.to_dict())