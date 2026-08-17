# backend/routes/empresa_routes.py
"""
Rotas publicas para cadastro de empresa + owner.
Este e o unico lugar onde Empresa pode ser criada via API.
"""
from flask import Blueprint, request

from config import Config
from services.empresa_service import criar_empresa_com_owner
from utils.api_response import error_response, success_response


empresa_routes = Blueprint('empresa_routes', __name__, url_prefix='/api/v1/empresas')


# POST /api/v1/empresas/registro -- Cria empresa + owner na mesma transacao
@empresa_routes.route('/registro', methods=['POST'])
def registro():
    """
    Fluxo de cadastro inicial:
    1. Pessoa informa dados da empresa + seus dados
    2. Backend cria Empresa + User (owner)
    3. Owner pode fazer login

    Body:
    {
        "empresa": {
            "nome": "Minha Empresa",
            "razao_social": "Minha Empresa Ltda",
            "cnpj": "12.345.678/0001-90",
            "email": "contato@empresa.com",
            "telefone": "11999999999"
        },
        "owner": {
            "nome": "João Silva",
            "email": "joao@empresa.com",
            "senha": "minhasenha123"
        }
    }
    """
    # Verifica se cadastro publico esta habilitado
    if not Config.SIGNUP_CODE:
        return error_response(
            'Cadastro publico desativado. Entre em contato com o administrador.',
            403
        )

    data = request.get_json(silent=True) or {}
    codigo = (data.get('codigo') or '').strip()

    # Valida codigo de acesso
    import secrets
    if not secrets.compare_digest(codigo, Config.SIGNUP_CODE):
        return error_response('Codigo de acesso invalido.', 401)

    try:
        result = criar_empresa_com_owner(data)
    except ValueError as exc:
        return error_response(str(exc), 400)

    return success_response(result, 'Empresa e conta criadas com sucesso.', 201)


# GET /api/v1/empresas/:slug -- Busca empresa por slug (publico, para tela de convite)
@empresa_routes.route('/<string:slug>', methods=['GET'])
def get_by_slug(slug: str):
    """Busca empresa publica por slug."""
    from models.empresa import Empresa

    empresa = Empresa.query.filter_by(slug=slug).first()
    if not empresa:
        return error_response('Empresa nao encontrada.', 404)

    # Retorna apenas dados publicos
    return success_response({
        'id': empresa.id,
        'nome': empresa.nome,
        'slug': empresa.slug
    })
