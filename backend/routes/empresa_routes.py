# backend/routes/empresa_routes.py
"""
Rotas publicas para cadastro de empresa + owner.
Este e o unico lugar onde Empresa pode ser criada via API.
"""
from flask import Blueprint, g, request

from config import Config
from models.empresa import Empresa
from models.user import User
from services.empresa_service import criar_empresa_com_owner
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
