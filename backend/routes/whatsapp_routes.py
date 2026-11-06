from flask import Blueprint, request

from extensions import limiter
from services import whatsapp_service as service
from services.permission_service import require_permission
from utils.api_response import error_response, success_response

whatsapp_routes = Blueprint('whatsapp_routes', __name__, url_prefix='/api/v1/whatsapp')
whatsapp_webhook_routes = Blueprint('whatsapp_webhook_routes', __name__, url_prefix='/api/v1/webhooks/whatsapp')


@whatsapp_routes.get('/integracao')
@require_permission('settings.read')
def show_integration():
    integration = service.get_integration()
    return success_response(integration.to_dict() if integration else None)


@whatsapp_routes.put('/integracao')
@require_permission('settings.update')
def save_integration():
    try:
        return success_response(service.save_integration(request.get_json(silent=True) or {}), 'Integracao WhatsApp salva.')
    except (RuntimeError, ValueError) as exc:
        return error_response(str(exc), 400)


@whatsapp_routes.delete('/integracao')
@require_permission('settings.update')
def delete_integration():
    return success_response(None, 'Integracao WhatsApp removida.') if service.delete_integration() else error_response('Integracao nao encontrada.', 404)


@whatsapp_routes.post('/integracao/testar')
@limiter.limit('10 per minute')
@require_permission('settings.update')
def test_integration():
    try:
        return success_response(service.test_integration(), 'Conexao com a Meta confirmada.')
    except ValueError as exc:
        return error_response(str(exc), 400)


@whatsapp_routes.get('/conversas')
@require_permission('messages.read')
def conversations():
    return success_response(service.list_conversations())


@whatsapp_routes.post('/conversas')
@require_permission('messages.send')
def create_conversation():
    try:
        item = service.create_conversation(request.get_json(silent=True) or {})
    except ValueError as exc:
        return error_response(str(exc), 400)
    return success_response(item, 'Conversa criada.', 201) if item else error_response('Cliente ou UC nao encontrado.', 404)


@whatsapp_routes.get('/conversas/<int:conversation_id>/mensagens')
@require_permission('messages.read')
def messages(conversation_id):
    items = service.list_messages(conversation_id)
    return success_response(items) if items is not None else error_response('Conversa nao encontrada.', 404)


@whatsapp_routes.post('/conversas/<int:conversation_id>/mensagens')
@require_permission('messages.send')
def send_message(conversation_id):
    try:
        item = service.send_text(conversation_id, request.get_json(silent=True) or {})
    except ValueError as exc:
        return error_response(str(exc), 400)
    return success_response(item, 'Mensagem enviada.') if item else error_response('Conversa nao encontrada.', 404)


@whatsapp_routes.post('/templates/<int:template_id>/submeter')
@require_permission('settings.update')
def submit_template(template_id):
    try:
        item = service.submit_template(template_id)
    except ValueError as exc:
        return error_response(str(exc), 400)
    return success_response(item, 'Template enviado para aprovacao da Meta.') if item else error_response('Template WhatsApp nao encontrado.', 404)


@whatsapp_routes.post('/templates/sincronizar')
@require_permission('settings.update')
def sync_templates():
    try:
        return success_response(service.sync_templates(), 'Status dos templates atualizado.')
    except ValueError as exc:
        return error_response(str(exc), 400)


@whatsapp_webhook_routes.get('')
def verify_webhook():
    challenge = service.webhook_challenge(request.args.get('hub.mode'), request.args.get('hub.verify_token'), request.args.get('hub.challenge'))
    return (challenge, 200, {'Content-Type': 'text/plain'}) if challenge is not None else ('', 403)


@whatsapp_webhook_routes.post('')
def receive_webhook():
    raw = request.get_data(cache=True)
    if not service.valid_webhook_signature(raw, request.headers.get('X-Hub-Signature-256')):
        return ('', 403)
    service.process_webhook(request.get_json(silent=True) or {})
    return ('', 200)
