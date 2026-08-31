# backend/routes/email_template_routes.py
from flask import Blueprint, g, request
import re

from extensions import limiter
from services.email_service import send_email
from services.email_template_service import (
    get_template,
    list_templates,
    renderizar,
    restaurar_padrao,
    update_template,
)
from services.permission_service import require_permission, require_role
from utils.api_response import error_response, success_response
from services.log_service import LogService

# Regex para validar formato de chave de template.
# Chaves válidas: começam com letra, seguido por alfanuméricos, hífen e underline.
# Exemplos: "welcome_email", "password_reset", "invoice_v2", "cliente-confirmacao"
# Inválidos: "123template", "template<script>", "template admin", "", " "
_TEMPLATE_CHAVE_PATTERN = re.compile(r'^[a-zA-Z][a-zA-Z0-9_-]*$')


def _validar_chave_template(chave: str) -> None:
    """
    Valida o formato de uma chave de template.

    Args:
        chave: string a ser validada

    Raises:
        ValueError: se a chave não estiver no formato aceito
    """
    if not chave or not isinstance(chave, str):
        raise ValueError('Chave é obrigatória e deve ser uma string.')

    chave = chave.strip()
    if not chave:
        raise ValueError('Chave não pode ser vazia.')

    if not _TEMPLATE_CHAVE_PATTERN.match(chave):
        raise ValueError(
            'Formato de chave inválido. Use apenas letras, números, hífen e underline, '
            'começando com uma letra. Exemplo: "welcome_email" ou "password-reset-v2".'
        )


email_template_routes = Blueprint('email_template_routes', __name__, url_prefix='/api/v1/email-templates')


@email_template_routes.route('', methods=['GET'])
@require_permission('settings.read')
def index():
    return success_response(list_templates())


@email_template_routes.route('/<string:chave>', methods=['GET'])
@require_permission('settings.read')
def show(chave: str):
    _validar_chave_template(chave)
    template = get_template(chave)
    if not template:
        return error_response('Template não encontrado.', 404)
    return success_response(template)


@email_template_routes.route('/<string:chave>', methods=['PUT'])
@require_permission('settings.update')
def update(chave: str):
    return error_response('Endpoint legado somente leitura; use /message-templates.', 410)
    _validar_chave_template(chave)
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
    return error_response('Endpoint legado somente leitura; use /message-templates.', 410)
    _validar_chave_template(chave)
    template = restaurar_padrao(chave)
    if not template:
        return error_response('Template não encontrado.', 404)
    return success_response(template, 'Template restaurado ao padrão.')


@email_template_routes.route('/<string:chave>/testar', methods=['POST'])
@require_role('owner', 'admin')
@limiter.limit('10 per minute')
def test_send(chave: str):
    return error_response('Envio de teste desativado; use preview local em /message-templates.', 410)
    """
    Envia um e-mail de teste para o usuário logado.

    RESTRIÇÕES DE SEGURANÇA:
    - Apenas owner e admin podem usar esta rota (não apenas settings.update)
    - Rate limit: 10 testes por minuto
    - Logs são gerados para cada teste enviado (auditoria)
    - O e-mail de teste é enviado SOMENTE para o próprio usuário logado
    """
    _validar_chave_template(chave)

    # Verifica se o template existe antes de tentar enviar (evita log de erro desnecessário)
    template_info = get_template(chave)
    if not template_info:
        return error_response('Template não encontrado.', 404)

    # Valores de exemplo -- o próprio usuário logado recebe o teste
    variaveis_exemplo = {
        'nome': g.current_user.nome or g.current_user.email,
        'link': 'https://exemplo.com/link-de-teste',
        'papel': g.current_user.role,
        'empresa': g.current_empresa.nome if g.current_empresa else 'HUB'
    }

    renderizado = renderizar(chave, variaveis_exemplo)
    if not renderizado:
        return error_response('Template não encontrado.', 404)

    assunto, html, text = renderizado
    enviado = send_email(
        to=g.current_user.email,
        subject=f'[TESTE] {assunto}',
        html=html,
        text=text,
    )

    # Log de auditoria para cada teste de e-mail
    LogService.info(
        acao='email_template_test',
        mensagem=f'Teste de e-mail para template "{chave}" enviado para {g.current_user.email}',
        entidade='EmailTemplate',
        entidade_id=chave,
        extra={
            'user_id': g.current_user.id,
            'user_email': g.current_user.email,
            'template': chave,
            'test_subject': f'[TESTE] {assunto}',
        }
    )

    if not enviado:
        return error_response('E-mail não enviado -- confira se RESEND_API_KEY está configurada.', 503)

    return success_response(None, f'E-mail de teste enviado para {g.current_user.email}.')
