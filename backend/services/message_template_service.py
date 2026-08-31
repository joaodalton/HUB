import re
from html import escape
from urllib.parse import urlsplit

from flask import g
from sqlalchemy.exc import IntegrityError

from extensions import db
from models.log_entry import LogEntry
from models.message_template import MessageTemplate

CHANNELS = frozenset({'email', 'whatsapp'})
ALLOWED_VARIABLES = frozenset({'nome', 'link', 'papel', 'empresa'})
KEY = re.compile(r'^[a-z][a-z0-9_-]{0,49}$')
PLACEHOLDER = re.compile(r'{{\s*([^{}\s]+)\s*}}')


def list_templates(canal=None):
    query = MessageTemplate.query.filter(MessageTemplate.empresa_id == g.current_empresa_id)
    if canal:
        _channel(canal); query = query.filter(MessageTemplate.canal == canal)
    return [item.to_dict() for item in query.order_by(MessageTemplate.canal, MessageTemplate.nome, MessageTemplate.id).all()]


def get_template(template_id):
    return MessageTemplate.query.filter_by(id=template_id, empresa_id=g.current_empresa_id).first()


def create(data):
    values = _validate(data, creating=True)
    item = MessageTemplate(empresa_id=g.current_empresa_id, padrao=False, origem_chave=None, **values)
    db.session.add(item)
    try: db.session.flush()
    except IntegrityError as exc: db.session.rollback(); raise ValueError('Já existe um template com esta chave neste canal.') from exc
    _audit('message_template_create', item); _commit_conflict()
    return item.to_dict()


def update(template_id, data):
    item = get_template(template_id)
    if not item: return None
    values = _validate({**item.to_dict(), **data}, creating=False)
    for key, value in values.items(): setattr(item, key, value)
    _audit('message_template_update', item); _commit_conflict()
    return item.to_dict()


def delete(template_id):
    item = get_template(template_id)
    if not item: return False
    identifier = item.id; channel = item.canal; key = item.chave
    db.session.delete(item)
    db.session.add(LogEntry(empresa_id=g.current_empresa_id, nivel='info', acao='message_template_delete', entidade='MessageTemplate', entidade_id=identifier, mensagem='Template removido', metadados={'canal': channel, 'chave': key}))
    db.session.commit(); return True


def restore(template_id):
    item = get_template(template_id)
    if not item or not item.padrao or not item.origem_chave: return None
    from services.email_template_service import get_template as get_legacy
    legacy = get_legacy(item.origem_chave)
    if not legacy: return None
    item.nome, item.assunto, item.corpo = legacy['nome'], legacy['assunto'], legacy['corpo']
    item.variaveis_permitidas = ','.join(legacy['variaveisDisponiveis'])
    _audit('message_template_restore', item); db.session.commit(); return item.to_dict()


def preview(template_id, variables):
    item = get_template(template_id)
    if not item: return None
    supplied = variables if isinstance(variables, dict) else {}
    allowed = set(_vars(item.variaveis_permitidas))
    if set(supplied) - allowed: raise ValueError('Variável não permitida para este template.')
    if 'link' in supplied and not _safe_link(supplied['link']): raise ValueError('Link deve ser uma URL HTTPS absoluta.')
    if set(PLACEHOLDER.findall(item.corpo)) - allowed or (item.canal == 'email' and set(PLACEHOLDER.findall(item.assunto)) - allowed): raise ValueError('Template contém variável não permitida.')
    rendered_body = _render_text(item.corpo, supplied)
    result = {'canal': item.canal, 'texto': rendered_body}
    if item.canal == 'email': result.update({'assunto': _render_text(item.assunto, supplied), 'html': '<div>' + escape(rendered_body).replace('\n', '<br>') + '</div>'})
    _audit('message_template_preview', item); db.session.commit(); return result


def render_email_for_empresa(empresa_id, chave, variables):
    seed_for_empresa(empresa_id)
    if 'link' in variables and not _safe_link(variables['link']):
        raise ValueError('Link deve ser uma URL HTTPS absoluta.')
    item = MessageTemplate.query.filter_by(empresa_id=empresa_id, canal='email', chave=chave).first()
    if not item: return None
    return _render_text(item.assunto, variables), '<div>' + escape(_render_text(item.corpo, variables)).replace('\n', '<br>') + '</div>', _render_text(item.corpo, variables)


def seed_for_empresa(empresa_id, *, commit=True):
    """Copia explicitamente defaults legados para tenant novo; não há fallback global."""
    from services.email_template_service import ensure_seeded
    from models.email_template import EmailTemplate
    if commit: ensure_seeded()
    existing = {row.chave for row in MessageTemplate.query.filter_by(empresa_id=empresa_id, canal='email').all()}
    for legacy in EmailTemplate.query.all():
        if legacy.chave not in existing:
            db.session.add(MessageTemplate(empresa_id=empresa_id, canal='email', chave=legacy.chave, nome=legacy.nome,
                assunto=legacy.assunto, corpo=legacy.corpo, variaveis_permitidas=legacy.variaveis_disponiveis or '', padrao=True, origem_chave=legacy.chave))
    if commit: db.session.commit()


def _validate(data, creating):
    channel = _channel(data.get('canal'))
    key = str(data.get('chave') or '').strip().lower()
    name, subject, body = str(data.get('nome') or '').strip(), str(data.get('assunto') or '').strip(), str(data.get('corpo') or '')
    variables = data.get('variaveisPermitidas', data.get('variaveis_permitidas', []))
    if isinstance(variables, str): variables = [x.strip() for x in variables.split(',') if x.strip()]
    if not KEY.fullmatch(key) or not name or len(name) > 150 or not body.strip() or len(body) > 10000: raise ValueError('Campos de template inválidos.')
    if channel == 'email' and (not subject or len(subject) > 255): raise ValueError('Assunto é obrigatório para e-mail.')
    if channel == 'whatsapp': subject = ''
    if not isinstance(variables, list) or len(variables) > len(ALLOWED_VARIABLES) or len(set(variables)) != len(variables) or set(variables) - ALLOWED_VARIABLES: raise ValueError('Variáveis permitidas inválidas.')
    found = set(PLACEHOLDER.findall(body)) | set(PLACEHOLDER.findall(subject))
    if found - set(variables) or _malformed_placeholder(body) or _malformed_placeholder(subject) or '<' in body or '>' in body or '<' in subject or '>' in subject: raise ValueError('Corpo, assunto ou variáveis inválidos.')
    return {'canal': channel, 'chave': key, 'nome': name, 'assunto': subject, 'corpo': body, 'variaveis_permitidas': ','.join(variables)}


def _channel(value):
    if value not in CHANNELS: raise ValueError('Canal inválido.')
    return value
def _vars(value): return [item for item in value.split(',') if item]
def _render_text(value, variables): return PLACEHOLDER.sub(lambda m: str(variables.get(m.group(1), m.group(0))), value)
def _malformed_placeholder(value): return '{{' in PLACEHOLDER.sub('', value) or '}}' in PLACEHOLDER.sub('', value)
def _safe_link(value):
    parsed=urlsplit(str(value)); return parsed.scheme == 'https' and bool(parsed.hostname) and not parsed.username and not parsed.password and not parsed.fragment
def _audit(action, item): db.session.add(LogEntry(empresa_id=g.current_empresa_id, nivel='info', acao=action, entidade='MessageTemplate', entidade_id=item.id, mensagem='Template atualizado', metadados={'canal': item.canal, 'chave': item.chave}))
def _commit_conflict():
    try: db.session.commit()
    except IntegrityError as exc: db.session.rollback(); raise ValueError('Já existe um template com esta chave neste canal.') from exc
