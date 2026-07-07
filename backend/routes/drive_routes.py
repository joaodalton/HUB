from flask import Blueprint, jsonify, request, send_file

from services.drive_service import drive_service
from utils.api_response import error_response


drive_routes = Blueprint('drive_routes', __name__)


@drive_routes.route('/search')
def search():
    query_text = request.args.get('q', '')
    return jsonify(drive_service.search_files(query_text))


@drive_routes.route('/download-zip', methods=['POST'])
def download_zip():
    data = request.get_json(silent=True) or {}
    file_ids = data.get('ids', [])

    if not file_ids:
        return error_response('Nenhum arquivo informado.', 400)

    zip_buffer = drive_service.create_reserved_zip(file_ids)

    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name='hub-reservados.zip'
    )
