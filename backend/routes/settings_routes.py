# backend/routes/settings_routes.py
from flask import Blueprint, request

from services.settings_service import get_all_settings, update_settings
from utils.api_response import success_response


settings_routes = Blueprint('settings_routes', __name__, url_prefix='/settings')


# GET /settings -- retorna tudo como {chave: valor}
@settings_routes.route('', methods=['GET'])
def index():
    return success_response(get_all_settings())


# PUT /settings -- Body: {chave: valor, ...}. Cria ou atualiza cada chave enviada.
@settings_routes.route('', methods=['PUT'])
def update():
    data = request.get_json(silent=True) or {}
    return success_response(update_settings(data), 'Configuracoes atualizadas.')