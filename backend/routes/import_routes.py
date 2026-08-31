from flask import Blueprint, request
from extensions import limiter
from services.import_service import criar_preview, confirmar
from services.permission_service import require_permission
from utils.api_response import error_response, success_response

import_routes = Blueprint('import_routes', __name__, url_prefix='/api/v1/importacoes')
@import_routes.route('/preview', methods=['POST'])
@limiter.limit('10 per minute')
@require_permission('imports.preview')
def preview():
    file = request.files.get('arquivo')
    if not file: return error_response('Arquivo é obrigatório.', 400)
    try: return success_response(criar_preview(file, request.form.get('tipo')), 'Preview criado.', 201)
    except ValueError as exc: return error_response(str(exc), 400)
@import_routes.route('/<int:preview_id>/confirmar', methods=['POST'])
@limiter.limit('5 per minute')
@require_permission('imports.commit')
def commit(preview_id):
    try: result=confirmar(preview_id)
    except ValueError as exc: return error_response(str(exc), 409)
    if not result: return error_response('Preview não encontrado.', 404)
    return success_response(result, 'Importação concluída.')
