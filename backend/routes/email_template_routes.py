# backend/routes/email_template_routes.py
from flask import Blueprint
import re

from extensions import limiter
from services.email_template_service import get_template, list_templates
from services.permission_service import require_permission, require_role
from utils.api_response import error_response, success_response

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


@email_template_routes.route('/<string:chave>/restaurar', methods=['POST'])
@require_permission('settings.update')
def restore(chave: str):
    return error_response('Endpoint legado somente leitura; use /message-templates.', 410)


@email_template_routes.route('/<string:chave>/testar', methods=['POST'])
@require_role('owner', 'admin')
@limiter.limit('10 per minute')
def test_send(chave: str):
    return error_response('Envio de teste desativado; use preview local em /message-templates.', 410)
