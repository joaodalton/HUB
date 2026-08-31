from flask import Blueprint, request
from services import message_template_service as service
from services.permission_service import require_permission
from utils.api_response import error_response, success_response

message_template_routes = Blueprint('message_template_routes', __name__, url_prefix='/api/v1/message-templates')
@message_template_routes.get('')
@require_permission('settings.read')
def index():
    try: return success_response(service.list_templates(request.args.get('canal')))
    except ValueError as exc: return error_response(str(exc), 400)
@message_template_routes.post('')
@require_permission('settings.update')
def create():
    try: return success_response(service.create(request.get_json(silent=True) or {}), 'Template criado.', 201)
    except ValueError as exc: return error_response(str(exc), 400)
@message_template_routes.get('/<int:template_id>')
@require_permission('settings.read')
def show(template_id):
    item=service.get_template(template_id); return success_response(item.to_dict()) if item else error_response('Template não encontrado.',404)
@message_template_routes.put('/<int:template_id>')
@require_permission('settings.update')
def update(template_id):
    try: item=service.update(template_id,request.get_json(silent=True) or {})
    except ValueError as exc: return error_response(str(exc),400)
    return success_response(item,'Template atualizado.') if item else error_response('Template não encontrado.',404)
@message_template_routes.delete('/<int:template_id>')
@require_permission('settings.update')
def delete(template_id): return success_response(None,'Template removido.') if service.delete(template_id) else error_response('Template não encontrado.',404)
@message_template_routes.post('/<int:template_id>/restaurar')
@require_permission('settings.update')
def restore(template_id):
    item=service.restore(template_id); return success_response(item,'Template restaurado.') if item else error_response('Template padrão não encontrado.',404)
@message_template_routes.post('/<int:template_id>/preview')
@require_permission('settings.update')
def preview(template_id):
    try: item=service.preview(template_id,(request.get_json(silent=True) or {}).get('variaveis',{}))
    except ValueError as exc: return error_response(str(exc),400)
    return success_response(item) if item else error_response('Template não encontrado.',404)
