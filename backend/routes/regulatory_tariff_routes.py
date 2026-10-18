from flask import Blueprint, g, request
from sqlalchemy.exc import OperationalError
from werkzeug.exceptions import RequestEntityTooLarge

from config import Config
from extensions import limiter
from services.log_service import LogService
from services.permission_service import require_platform_admin
from services.aneel_ckan_client import AneelCkanInvalidResponse, AneelCkanUnavailable
from services.regulatory_tariff_import_service import UploadTooLarge, confirm, create_ckan_preview, create_preview, status
from utils.api_response import error_response, success_response


regulatory_tariff_routes = Blueprint('regulatory_tariff_routes', __name__, url_prefix='/api/v1/regulatory-tariffs')


@regulatory_tariff_routes.get('/status')
@require_platform_admin()
def get_status():
    try:
        return success_response(status())
    except OperationalError:
        return error_response('Base regulatória indisponível. Tente novamente mais tarde.', 503)


@regulatory_tariff_routes.post('/imports/preview')
@limiter.limit('10 per minute')
@require_platform_admin()
def preview():
    # Limite por rota: PDFs e outros multipart permanecem com seus próprios limites.
    request.max_content_length = Config.REGULATORY_TARIFF_MAX_BYTES + 1024 * 1024
    try:
        result = create_preview(request.files.get('arquivo'), request.form.get('sourceUrl'), request.form.get('sourceVersion'))
    except RequestEntityTooLarge:
        return error_response('Arquivo excede o limite de 100 MiB.', 413)
    except UploadTooLarge:
        return error_response('Arquivo excede o limite de 100 MiB.', 413)
    except ValueError as exc:
        return error_response(str(exc), 400)
    except OperationalError:
        return error_response('Base regulatória indisponível. Tente novamente mais tarde.', 503)
    return success_response(result, 'Prévia regulatória criada.', 201)


@regulatory_tariff_routes.post('/imports/ckan/preview')
@limiter.limit('10 per minute')
@require_platform_admin()
def preview_ckan():
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return error_response('Corpo JSON inválido.', 400)
    try:
        result = create_ckan_preview(body.get('distributor'), body.get('year'))
    except AneelCkanUnavailable as exc:
        LogService.warning('regulatory_tariff_ckan_failed', 'Consulta CKAN ANEEL indisponível.',
                           entidade='RegulatoryTariff', metadados={'createdById': g.current_user.id,
                           'distributor': body.get('distributor'), 'year': body.get('year')})
        return error_response(str(exc), 503)
    except AneelCkanInvalidResponse as exc:
        LogService.error('regulatory_tariff_ckan_failed', 'Resposta CKAN ANEEL inválida.',
                         entidade='RegulatoryTariff', metadados={'createdById': g.current_user.id,
                         'distributor': body.get('distributor'), 'year': body.get('year')})
        return error_response(str(exc), 502)
    except ValueError as exc:
        return error_response(str(exc), 400)
    except OperationalError:
        return error_response('Base regulatória indisponível. Tente novamente mais tarde.', 503)
    return success_response(result, 'Prévia regulatória criada pela API ANEEL.', 201)


@regulatory_tariff_routes.post('/imports/confirm')
@limiter.limit('5 per minute')
@require_platform_admin()
def confirm_import():
    body = request.get_json(silent=True) or {}
    preview_id = body.get('previewId')
    if type(preview_id) is not int or preview_id <= 0:
        return error_response('previewId inválido.', 400)
    try:
        result = confirm(preview_id)
    except ValueError as exc:
        return error_response(str(exc), 409)
    except OperationalError:
        return error_response('Base regulatória indisponível. Tente novamente mais tarde.', 503)
    if result is None:
        return error_response('Prévia não encontrada.', 404)
    return success_response(result, 'Importação regulatória concluída.')
