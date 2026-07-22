from flask import Blueprint, jsonify, request, send_file

from services.drive_service import get_drive_service
from utils.api_response import error_response


drive_routes = Blueprint('drive_routes', __name__)


def _resolve_service():
    """Retorna (service, None) se o Drive estiver configurado, ou (None, response_de_erro)
    se credentials.json faltar/for invalido -- nunca deixa a rota crashar com 500 cru."""
    try:
        return get_drive_service(), None
    except Exception as exc:
        return None, error_response(f'Google Drive nao configurado: {exc}', 503)


@drive_routes.route('/search')
def search():
    service, error = _resolve_service()
    if error:
        return error

    query_text = request.args.get('q', '')
    return jsonify(service.search_files(query_text))


@drive_routes.route('/download-zip', methods=['POST'])
def download_zip():
    service, error = _resolve_service()
    if error:
        return error

    data = request.get_json(silent=True) or {}
    file_ids = data.get('ids', [])

    if not file_ids:
        return error_response('Nenhum arquivo informado.', 400)

    zip_buffer = service.create_reserved_zip(file_ids)

    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name='hub-reservados.zip'
    )