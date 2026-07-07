from flask import Blueprint, request

from services.database_config_service import (
    get_database_config,
    save_google_drive_config,
    save_provider,
    save_sql_config,
    test_database_config
)
from utils.api_response import error_response, success_response


config_routes = Blueprint('config_routes', __name__, url_prefix='/config')


@config_routes.route('/database')
def database_config():
    return success_response(get_database_config())


@config_routes.route('/database/provider', methods=['POST'])
def update_provider():
    data = request.get_json(silent=True) or {}

    try:
        config = save_provider(data.get('provider', ''))
    except ValueError as exc:
        return error_response(str(exc), 400)

    return success_response(config, 'Provedor atualizado.')


@config_routes.route('/database/google-drive', methods=['POST'])
def update_google_drive():
    data = request.get_json(silent=True) or {}
    return success_response(save_google_drive_config(data), 'Google Drive configurado.')


@config_routes.route('/database/sql', methods=['POST'])
def update_sql():
    data = request.get_json(silent=True) or {}
    return success_response(save_sql_config(data), 'SQL configurado.')


@config_routes.route('/database/test', methods=['POST'])
def test_database():
    data = request.get_json(silent=True) or {}
    ok, message = test_database_config(data.get('provider', ''))
    status = 200 if ok else 400

    return success_response({'ok': ok}, message, status)
