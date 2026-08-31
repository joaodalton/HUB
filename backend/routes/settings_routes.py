# backend/routes/settings_routes.py
from flask import Blueprint, g, request

from services.settings_service import get_all_settings, update_settings
from services.drive_service import invalidate_drive_cache
from services.permission_service import require_permission
from utils.api_response import success_response


settings_routes = Blueprint('settings_routes', __name__, url_prefix='/api/v1/settings')


# GET /api/v1/settings -- retorna tudo como {chave: valor}
@settings_routes.route('', methods=['GET'])
@require_permission('settings.read')
def index():
    return success_response(get_all_settings())


# PUT /api/v1/settings -- Body: {chave: valor, ...}. Cria ou atualiza cada chave enviada.
@settings_routes.route('', methods=['PUT'])
@require_permission('settings.update')
def update():
    data = request.get_json(silent=True) or {}
    settings = update_settings(data)
    if 'google_drive_root_folder_id' in data:
        invalidate_drive_cache(g.current_empresa_id)
    return success_response(settings, 'Configuracoes atualizadas.')
