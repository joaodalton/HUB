# backend/routes/empresa_routes.py
"""
Rotas publicas para cadastro de empresa + owner.
Este e o unico lugar onde Empresa pode ser criada via API.
"""
from flask import Blueprint, g, request

from config import Config
from models.empresa import Empresa
from models.user import User
from services.empresa_service import (
    criar_empresa_com_owner, get_empresa_atual, get_empresa_documentos,
    set_empresa_documento, update_empresa_atual, update_empresa_platform,
)
from services.permission_service import require_permission
from utils.api_response import error_response, success_response


empresa_routes = Blueprint('empresa_routes', __name__, url_prefix='/api/v1/empresas')


def _require_platform_admin():
    if not g.current_user.is_platform_admin:
        return error_response('Acesso restrito ao administrador da plataforma.', 403)
    return None


@empresa_routes.route('', methods=['GET'])
def index():
    """Lista empresas apenas para quem opera a plataforma."""
    denied = _require_platform_admin()
    if denied:
        return denied

    empresas = Empresa.query.order_by(Empresa.created_at.desc()).all()
    result = []
    for empresa in empresas:
        result.append({
            **empresa.to_dict(),
            'totalUsuarios': User.query.filter_by(empresa_id=empresa.id).count()
        })
    return success_response(result)


@empresa_routes.route('', methods=['POST'])
def criar():
    denied = _require_platform_admin()
    if denied:
        return denied
    try:
        return success_response(criar_empresa_com_owner(request.get_json(silent=True) or {}), 'Empresa criada.', 201)
    except ValueError as exc:
        return error_response(str(exc), 400)


@empresa_routes.route('/<int:empresa_id>', methods=['PUT'])
def atualizar_qualquer(empresa_id: int):
    denied = _require_platform_admin()
    if denied:
        return denied
    try:
        empresa = update_empresa_platform(empresa_id, request.get_json(silent=True) or {})
    except ValueError as exc:
        return error_response(str(exc), 400)
    if not empresa:
        return error_response('Empresa nao encontrada.', 404)
    return success_response(empresa, 'Empresa atualizada.')


# POST /api/v1/empresas/registro -- Cria empresa + owner na mesma transacao
@empresa_routes.route('/registro', methods=['POST'])
def registro():
    # Desativado por decisão (2026-08-19): criação de empresa é sempre
    # manual, via backend/scripts/criar_empresa.py -- nunca um formulário
    # público, mesmo com código de acesso. SIGNUP_CODE não protege mais
    # esta rota (reuso indevido, ver Issue "SIGNUP_CODE reuso"). Modelo
    # futuro (planos pagos): link de convite enviado por e-mail após a
    # compra, criando empresa + owner juntos -- continua sem formulário
    # público exposto.
    return error_response(
        'Cadastro público de empresa desativado. Empresas são criadas manualmente -- '
        'ver backend/scripts/criar_empresa.py.',
        403
    )


@empresa_routes.route('/atual', methods=['GET'])
@require_permission('empresa.read')
def atual():
    empresa = get_empresa_atual()
    if not empresa:
        return error_response('Empresa nao encontrada.', 404)
    return success_response(empresa)


@empresa_routes.route('/atual', methods=['PUT'])
@require_permission('empresa.update')
def atualizar_atual():
    try:
        empresa = update_empresa_atual(request.get_json(silent=True) or {})
    except ValueError as exc:
        return error_response(str(exc), 400)
    if not empresa:
        return error_response('Empresa nao encontrada.', 404)
    return success_response(empresa, 'Dados da empresa atualizados.')


# GET /api/v1/empresas/:slug -- Busca empresa por slug (publico, para tela de convite)
@empresa_routes.route('/<string:slug>', methods=['GET'])
def get_by_slug(slug: str):
    """Busca empresa publica por slug."""
    empresa = Empresa.query.filter_by(slug=slug).first()
    if not empresa:
        return error_response('Empresa nao encontrada.', 404)

    # Retorna apenas dados publicos
    return success_response({
        'id': empresa.id,
        'nome': empresa.nome,
        'slug': empresa.slug
    })


# GET /api/v1/empresas/documentos -- documentos fixos (CNPJ/Estatuto) da empresa do usuario logado
@empresa_routes.route('/documentos', methods=['GET'])
@require_permission('settings.read')
def documentos():
    try:
        return success_response(get_empresa_documentos(g.current_empresa_id))
    except ValueError as exc:
        return error_response(str(exc), 404)


# POST /api/v1/empresas/documentos/<tipo> -- multipart/form-data, campo 'arquivo'. tipo: cnpj | estatuto
@empresa_routes.route('/documentos/<string:tipo>', methods=['POST'])
@require_permission('settings.update')
def upload_documento(tipo: str):
    if 'arquivo' not in request.files or not request.files['arquivo'].filename:
        return error_response('Nenhum arquivo enviado.', 400)

    try:
        resultado = set_empresa_documento(g.current_empresa_id, tipo, request.files['arquivo'])
    except ValueError as exc:
        return error_response(str(exc), 400)
    except Exception as exc:
        # Mesmo padrao do document_routes.py -- credentials.json ausente, conta
        # OAuth sem token valido etc. nunca vira 500 cru, vira "servico indisponivel".
        return error_response(f'Google Drive nao configurado ou indisponivel: {exc}', 503)

    return success_response(resultado, 'Documento atualizado.')
