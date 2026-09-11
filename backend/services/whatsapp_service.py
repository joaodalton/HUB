"""Meta Cloud API adapter. Segredos permanecem em ApiCredential cifrada."""
import hashlib
import hmac
import re
from datetime import datetime

import requests
from flask import g
from sqlalchemy.exc import IntegrityError

from config import Config
from extensions import db
from models.api_credential import ApiCredential
from models.client import Client
from models.consumer_unit import ConsumerUnit
from models.message_template import MessageTemplate
from models.whatsapp import WhatsappConversation, WhatsappIntegration, WhatsappMessage

PHONE = re.compile(r'^\d{10,15}$')
META_CATEGORIES = frozenset({'MARKETING', 'UTILITY', 'AUTHENTICATION'})
META_STATUSES = frozenset({'draft', 'pending', 'approved', 'rejected'})


class MetaApiError(ValueError):
    pass


def get_integration():
    return WhatsappIntegration.query.filter_by(empresa_id=g.current_empresa_id).first()


def save_integration(data):
    phone_number_id = _required_identifier(data.get('phoneNumberId'), 'Phone Number ID')
    business_account_id = _required_identifier(data.get('businessAccountId'), 'WhatsApp Business Account ID')
    access_token = data.get('accessToken')
    integration = get_integration()
    if not integration and not isinstance(access_token, str):
        raise ValueError('Token permanente da Meta e obrigatorio na primeira configuracao.')
    if integration:
        credential = integration.credential
    else:
        credential = ApiCredential(empresa_id=g.current_empresa_id, provider='whatsapp', nome='Meta Cloud API', segredo_encrypted='')
        integration = WhatsappIntegration(empresa_id=g.current_empresa_id, credential=credential, phone_number_id=phone_number_id, business_account_id=business_account_id)
        db.session.add(integration)
    if isinstance(access_token, str):
        if not access_token.strip():
            raise ValueError('Token permanente invalido.')
        credential.set_segredo(access_token.strip())
    integration.phone_number_id = phone_number_id
    integration.business_account_id = business_account_id
    integration.display_phone_number = _optional(data.get('displayPhoneNumber'), 40)
    integration.enabled = bool(data.get('enabled', True))
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ValueError('Este Phone Number ID ja esta conectado a outra empresa.') from exc
    return integration.to_dict()


def delete_integration():
    integration = get_integration()
    if not integration:
        return False
    credential = integration.credential
    db.session.delete(integration)
    db.session.delete(credential)
    db.session.commit()
    return True


def test_integration():
    integration = _configured_integration()
    result = _meta_request('GET', f'/{integration.phone_number_id}', integration, params={'fields': 'display_phone_number,verified_name'})
    integration.display_phone_number = result.get('display_phone_number') or integration.display_phone_number
    integration.verified_name = result.get('verified_name') or integration.verified_name
    db.session.commit()
    return integration.to_dict()


def list_conversations():
    rows = WhatsappConversation.query.filter_by(empresa_id=g.current_empresa_id).order_by(
        WhatsappConversation.last_message_at.desc(), WhatsappConversation.id.desc()
    ).all()
    return [row.to_dict(last_message=_last_message(row.id)) for row in rows]


def create_conversation(data):
    client = None
    client_id = data.get('clientId')
    if client_id is not None:
        client = Client.query.filter_by(id=client_id, empresa_id=g.current_empresa_id).first()
        if not client:
            return None
    phone = _phone(data.get('phoneNumber') or (client.telefone if client else ''))
    unit = None
    if data.get('consumerUnitId') is not None:
        unit = ConsumerUnit.query.filter_by(id=data['consumerUnitId'], empresa_id=g.current_empresa_id).first()
        if not unit or (client and unit.client_id != client.id):
            return None
    existing = WhatsappConversation.query.filter_by(empresa_id=g.current_empresa_id, phone_number=phone).first()
    if existing:
        return existing.to_dict(last_message=_last_message(existing.id))
    row = WhatsappConversation(
        empresa_id=g.current_empresa_id, client_id=client.id if client else None,
        consumer_unit_id=unit.id if unit else None, phone_number=phone,
        contact_name=_optional(data.get('contactName'), 150) or (client.nome if client else None),
    )
    db.session.add(row)
    db.session.commit()
    return row.to_dict()


def list_messages(conversation_id):
    conversation = _conversation(conversation_id)
    if not conversation:
        return None
    conversation.unread_count = 0
    db.session.commit()
    return [row.to_dict() for row in WhatsappMessage.query.filter_by(
        empresa_id=g.current_empresa_id, conversation_id=conversation.id
    ).order_by(WhatsappMessage.created_at.asc(), WhatsappMessage.id.asc()).all()]


def send_text(conversation_id, data):
    conversation = _conversation(conversation_id)
    if not conversation:
        return None
    body = str(data.get('body') or '').strip()
    if not body or len(body) > 4096:
        raise ValueError('Mensagem deve ter entre 1 e 4096 caracteres.')
    message = WhatsappMessage(empresa_id=g.current_empresa_id, conversation_id=conversation.id,
        direction='outbound', message_type='text', body=body, status='queued')
    db.session.add(message)
    db.session.commit()
    try:
        integration = _configured_integration()
        result = _meta_request('POST', f'/{integration.phone_number_id}/messages', integration, json={
            'messaging_product': 'whatsapp', 'to': conversation.phone_number, 'type': 'text', 'text': {'body': body},
        })
        message.meta_message_id = ((result.get('messages') or [{}])[0]).get('id')
        message.status = 'sent'
        message.sent_at = datetime.utcnow()
        conversation.last_message_at = message.sent_at
        db.session.commit()
        return message.to_dict()
    except MetaApiError as exc:
        message.status, message.provider_error = 'failed', str(exc)[:500]
        db.session.commit()
        raise


def submit_template(template_id):
    template = _template(template_id)
    if not template:
        return None
    if template.meta_status not in {'draft', 'rejected'}:
        raise ValueError('Apenas templates em rascunho ou rejeitados podem ser enviados para aprovacao.')
    category = (template.meta_category or 'UTILITY').upper()
    if category not in META_CATEGORIES:
        raise ValueError('Categoria Meta invalida.')
    integration = _configured_integration()
    variables = _variables(template)
    component = {'type': 'BODY', 'text': _meta_body(template.corpo, variables)}
    if variables:
        component['example'] = {'body_text': [[_sample(variable) for variable in variables]]}
    result = _meta_request('POST', f'/{integration.business_account_id}/message_templates', integration, json={
        'name': template.chave.replace('-', '_'), 'language': 'pt_BR', 'category': category, 'components': [component],
    })
    template.meta_status = str(result.get('status') or 'pending').lower()
    template.meta_template_id = str(result.get('id') or '') or None
    template.meta_category = category
    template.meta_rejection_reason = None
    template.meta_submitted_at = datetime.utcnow()
    db.session.commit()
    return template.to_dict()


def sync_templates():
    integration = _configured_integration()
    result = _meta_request('GET', f'/{integration.business_account_id}/message_templates', integration,
        params={'fields': 'id,name,status,category,rejected_reason', 'limit': 1000})
    remote = {str(item.get('name')): item for item in result.get('data', [])}
    templates = MessageTemplate.query.filter_by(empresa_id=g.current_empresa_id, canal='whatsapp').all()
    for template in templates:
        item = remote.get(template.chave.replace('-', '_'))
        if item:
            template.meta_template_id = str(item.get('id') or '') or template.meta_template_id
            template.meta_status = str(item.get('status') or 'pending').lower()
            template.meta_category = item.get('category') or template.meta_category
            template.meta_rejection_reason = item.get('rejected_reason')
    db.session.commit()
    return [item.to_dict() for item in templates]


def process_webhook(payload):
    for entry in payload.get('entry', []):
        for change in entry.get('changes', []):
            value = change.get('value') or {}
            phone_id = ((value.get('metadata') or {}).get('phone_number_id'))
            integration = WhatsappIntegration.query.filter_by(phone_number_id=str(phone_id or '')).first()
            if not integration:
                continue
            for status in value.get('statuses') or []:
                _update_delivery(status, integration.empresa_id)
            for incoming in value.get('messages') or []:
                _store_incoming(incoming, value.get('contacts') or [], integration)
    db.session.commit()


def valid_webhook_signature(raw, header):
    secret = Config.META_APP_SECRET
    if not secret or not header or not header.startswith('sha256='):
        return False
    expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(header[7:], expected)


def webhook_challenge(mode, token, challenge):
    if mode == 'subscribe' and Config.META_WEBHOOK_VERIFY_TOKEN and hmac.compare_digest(token or '', Config.META_WEBHOOK_VERIFY_TOKEN):
        return challenge
    return None


def _store_incoming(incoming, contacts, integration):
    meta_id = str(incoming.get('id') or '')
    if not meta_id or WhatsappMessage.query.filter_by(meta_message_id=meta_id).first():
        return
    phone = _phone(incoming.get('from'))
    client = Client.query.filter_by(empresa_id=integration.empresa_id, telefone=phone).first()
    contact = next((item for item in contacts if str(item.get('wa_id')) == phone), {})
    conversation = WhatsappConversation.query.filter_by(empresa_id=integration.empresa_id, phone_number=phone).first()
    if not conversation:
        conversation = WhatsappConversation(empresa_id=integration.empresa_id, phone_number=phone,
            client_id=client.id if client else None, contact_name=((contact.get('profile') or {}).get('name')) or (client.nome if client else None))
        db.session.add(conversation); db.session.flush()
    body = ((incoming.get('text') or {}).get('body')) or ''
    timestamp = datetime.utcfromtimestamp(int(incoming.get('timestamp') or datetime.utcnow().timestamp()))
    db.session.add(WhatsappMessage(empresa_id=integration.empresa_id, conversation_id=conversation.id,
        direction='inbound', message_type=incoming.get('type') or 'text', body=body, status='received', meta_message_id=meta_id, sent_at=timestamp))
    conversation.last_message_at, conversation.unread_count = timestamp, conversation.unread_count + 1


def _update_delivery(status, empresa_id):
    message = WhatsappMessage.query.filter_by(meta_message_id=str(status.get('id') or ''), empresa_id=empresa_id).first()
    state = str(status.get('status') or '')
    if not message or state not in {'sent', 'delivered', 'read', 'failed'}:
        return
    message.status = state
    at = datetime.utcfromtimestamp(int(status.get('timestamp') or datetime.utcnow().timestamp()))
    if state == 'delivered': message.delivered_at = at
    if state == 'read': message.read_at = at
    if state == 'failed': message.provider_error = str(status.get('errors') or 'Falha informada pela Meta')[:500]


def _configured_integration():
    integration = get_integration()
    if not integration or not integration.enabled or not integration.credential or not integration.credential.get_segredo():
        raise MetaApiError('WhatsApp Meta Cloud API nao esta configurado para esta empresa.')
    return integration


def _meta_request(method, path, integration, **kwargs):
    try:
        response = requests.request(method, f'{Config.META_GRAPH_API_BASE_URL.rstrip("/")}/{Config.META_GRAPH_API_VERSION}{path}',
            headers={'Authorization': f'Bearer {integration.credential.get_segredo()}'}, timeout=20, **kwargs)
    except requests.RequestException as exc:
        raise MetaApiError('Nao foi possivel comunicar com a Meta. Tente novamente.') from exc
    try:
        data = response.json()
    except ValueError:
        data = {}
    if not response.ok:
        error = data.get('error') or {}
        raise MetaApiError(str(error.get('message') or 'A Meta recusou a solicitacao.')[:500])
    return data


def _conversation(conversation_id):
    return WhatsappConversation.query.filter_by(id=conversation_id, empresa_id=g.current_empresa_id).first()


def _template(template_id):
    return MessageTemplate.query.filter_by(id=template_id, empresa_id=g.current_empresa_id, canal='whatsapp').first()


def _last_message(conversation_id):
    return WhatsappMessage.query.filter_by(empresa_id=g.current_empresa_id, conversation_id=conversation_id).order_by(WhatsappMessage.created_at.desc(), WhatsappMessage.id.desc()).first()


def _phone(value):
    phone = re.sub(r'\D', '', str(value or ''))
    if not PHONE.fullmatch(phone):
        raise ValueError('Telefone WhatsApp invalido. Informe DDI e DDD.')
    return phone


def _required_identifier(value, label):
    identifier = str(value or '').strip()
    if not identifier or len(identifier) > 100 or not re.fullmatch(r'[A-Za-z0-9_-]+', identifier):
        raise ValueError(f'{label} invalido.')
    return identifier


def _optional(value, size):
    text = str(value or '').strip()
    return text[:size] or None


def _variables(template):
    return [value for value in template.variaveis_permitidas.split(',') if value]


def _meta_body(body, variables):
    result = body
    for index, variable in enumerate(variables, start=1):
        result = re.sub(r'{{\s*' + re.escape(variable) + r'\s*}}', '{{' + str(index) + '}}', result)
    return result


def _sample(variable):
    return {'nome': 'Joao', 'empresa': 'Empresa', 'papel': 'cliente', 'link': 'https://example.com'}.get(variable, 'exemplo')
