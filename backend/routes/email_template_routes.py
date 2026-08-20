# backend/routes/email_template_routes.py
from flask import Blueprint, g, request

from services.email_service import send_email
from services.email_template_service import get_template, list_templates, renderizar, restaurar_padrao, update_template
from services.permission_service import require_permission
from utils.api_response import error_response, success_response


email_template_routes = Blueprint('email_template_routes', __name__, url_prefix='/api/v1/email-templates')


@email_template_routes.route('', methods=['GET'])
@require_permission('settings.read')
def index():
    return success_response(list_templates())


@email_template_routes.route('/<string:chave>', methods=['GET'])
@require_permission('settings.read')
def show(chave: str):
    template = get_template(chave)
    if not template:
        return error_response('Template não encontrado.', 404)
    return success_response(template)


@email_template_routes.route('/<string:chave>', methods=['PUT'])
@require_permission('settings.update')
def update(chave: str):
    data = request.get_json(silent=True) or {}
    assunto = (data.get('assunto') or '').strip()
    corpo = data.get('corpo') or ''

    if not assunto:
        return error_response('Assunto é obrigatório.', 400)
    if not corpo.strip():
        return error_response('Corpo é obrigatório.', 400)

    template = update_template(chave, assunto, corpo)
    if not template:
        return error_response('Template não encontrado.', 404)
    return success_response(template, 'Template atualizado.')


@email_template_routes.route('/<string:chave>/restaurar', methods=['POST'])
@require_permission('settings.update')
def restore(chave: str):
    template = restaurar_padrao(chave)
    if not template:
        return error_response('Template não encontrado.', 404)
    return success_response(template, 'Template restaurado ao padrão.')


@email_template_routes.route('/<string:chave>/testar', methods=['POST'])
@require_permission('settings.update')
def test_send(chave: str):
    # Valores de exemplo -- o proprio usuario logado recebe o teste, pra
    # conferir o resultado de verdade na caixa de entrada.
    variaveis_exemplo = {
        'nome': g.current_user.nome or g.current_user.email,
        'link': 'https://exemplo.com/link-de-teste',
        'papel': 'viewer',
        'empresa': g.current_empresa.nome if g.current_empresa else 'HUB'
    }

    renderizado = renderizar(chave, variaveis_exemplo)
    if not renderizado:
        return error_response('Template não encontrado.', 404)

    assunto, html, text = renderizado
    enviado = send_email(to=g.current_user.email, subject=f'[TESTE] {assunto}', html=html, text=text)

    if not enviado:
        return error_response('E-mail não enviado -- confira se RESEND_API_KEY está configurada.', 503)

    return success_response(None, f'E-mail de teste enviado para {g.current_user.email}.')