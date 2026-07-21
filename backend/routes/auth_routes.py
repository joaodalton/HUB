# backend/routes/auth_routes.py
from flask import Blueprint, request

from models.user import User
from services.auth_service import authenticate, create_first_admin
from utils.api_response import error_response, success_response


auth_routes = Blueprint('auth_routes', __name__, url_prefix='/auth')


@auth_routes.route('/bootstrap', methods=['POST'])
def bootstrap():
    # So funciona uma vez -- depois que existir 1 usuario, essa rota sempre nega.
    # Fica publica de proposito (nao precisa de token pra criar o primeiro admin),
    # e isso e seguro porque ela se tranca sozinha depois do primeiro uso.
    if User.query.count() > 0:
        return error_response('Bootstrap ja foi usado. Faca login em /auth/login.', 403)

    data = request.get_json(silent=True) or {}
    email = data.get('email', '').strip()
    senha = data.get('senha', '')

    if not email or not senha:
        return error_response('Email e senha sao obrigatorios.', 400)
    if len(senha) < 6:
        return error_response('Senha precisa ter pelo menos 6 caracteres.', 400)

    user = create_first_admin(email, senha)
    return success_response(user.to_dict(), 'Usuario admin criado. Faca login em /auth/login.', 201)


@auth_routes.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    email = data.get('email', '').strip()
    senha = data.get('senha', '')

    if not email or not senha:
        return error_response('Email e senha sao obrigatorios.', 400)

    result = authenticate(email, senha)

    if not result:
        return error_response('Email ou senha invalidos.', 401)

    return success_response(result, 'Login realizado.')