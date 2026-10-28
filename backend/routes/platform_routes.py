# backend/routes/platform_routes.py
"""
Rotas exclusivas do administrador da plataforma (User.is_platform_admin) --
permitem listar todas as empresas e "entrar" numa delas pra visualizar/
gerenciar os dados dela, continuando como o mesmo usuário logado.

"Entrar" numa empresa grava um cookie separado (hub_platform_view) com o
empresa_id escolhido; o middleware de auth (utils/auth.py) usa esse cookie
pra sobrescrever g.current_empresa_id só pra esse usuário. "Sair" remove o
cookie e volta pra empresa "de casa" (User.empresa_id).
"""
from flask import Blueprint, g, jsonify
from sqlalchemy import func

from extensions import db
from models.client import Client
from models.consumer_unit import ConsumerUnit
from models.empresa import Empresa
from models.plant import Plant
from models.user import User
from services.empresa_service import _sem_filtro_de_tenant_ambiente, excluir_empresa
from services.log_service import LogService
from services.neon_service import NeonError, get_storage_summary
from services.permission_service import require_platform_access, require_platform_admin
from utils.api_response import error_response, success_response
from utils.auth import clear_platform_view_cookie, set_platform_view_cookie
from config import Config


platform_routes = Blueprint('platform_routes', __name__, url_prefix='/api/v1/platform')


@platform_routes.route('', methods=['GET'])
@require_platform_access()
def overview():
    return success_response({
        'totalEmpresas': db.session.query(func.count(Empresa.id)).scalar() or 0,
        'totalUsuarios': db.session.query(func.count(User.id)).scalar() or 0,
    })


@platform_routes.route('/empresas', methods=['GET'])
@require_platform_access()
def listar_empresas():
    empresas = Empresa.query.order_by(Empresa.nome).all()

    # Client/ConsumerUnit/Plant sao TenantMixin: o filtro automatico de
    # tenant (extensions.py) restringiria a contagem a empresa do admin
    # logado. Precisamos contar entre todas as empresas aqui.
    with _sem_filtro_de_tenant_ambiente():
        clientes_por_empresa = dict(
            db.session.query(Client.empresa_id, func.count(Client.id)).group_by(Client.empresa_id).all()
        )
        ucs_por_empresa = dict(
            db.session.query(ConsumerUnit.empresa_id, func.count(ConsumerUnit.id)).group_by(ConsumerUnit.empresa_id).all()
        )
        usinas_por_empresa = dict(
            db.session.query(Plant.empresa_id, func.count(Plant.id)).group_by(Plant.empresa_id).all()
        )

    return success_response([{
        'id': empresa.id,
        'nome': empresa.nome,
        'slug': empresa.slug,
        'status': empresa.status,
        'totalClientes': clientes_por_empresa.get(empresa.id, 0),
        'totalUcs': ucs_por_empresa.get(empresa.id, 0),
        'totalUsinas': usinas_por_empresa.get(empresa.id, 0),
        'createdAt': empresa.created_at.isoformat() if empresa.created_at else None,
    } for empresa in empresas])


@platform_routes.route('/empresas/<int:empresa_id>', methods=['DELETE'])
@require_platform_admin()
def excluir_empresa_route(empresa_id: int):
    try:
        excluida = excluir_empresa(empresa_id)
    except ValueError as exc:
        return error_response(str(exc), 409, code='EMPRESA_NOT_EMPTY')

    if not excluida:
        return error_response('Empresa nao encontrada.', 404)

    return success_response(None, message='Empresa excluida com sucesso.')


@platform_routes.route('/empresas/<int:empresa_id>/entrar', methods=['POST'])
@require_platform_access()
def entrar_na_empresa(empresa_id: int):
    empresa = db.session.get(Empresa, empresa_id)

    if not empresa:
        return error_response('Empresa nao encontrada.', 404)

    try:
        LogService.info(
            acao='platform_enter_tenant',
            mensagem=f'Administrador da plataforma entrou na empresa {empresa.id}.',
            entidade='Empresa',
            entidade_id=empresa.id,
            metadados={'platformAdminUserId': g.current_user.id, 'empresaId': empresa.id},
            empresa_id=empresa.id,
            strict=True,
        )
    except Exception:
        return error_response('Falha ao registrar auditoria da plataforma.', 500, code='PLATFORM_AUDIT_FAILED')

    response = jsonify({
        'success': True,
        'message': f'Visualizando "{empresa.nome}".',
        'data': {
            'id': empresa.id,
            'nome': empresa.nome,
            'status': empresa.status,
        },
    })
    set_platform_view_cookie(response, empresa.id, g.current_user.id)
    return response


@platform_routes.route('/neon-storage', methods=['GET'])
@require_platform_admin()
def neon_storage():
    try:
        ambientes = get_storage_summary()
    except NeonError as exc:
        return error_response(str(exc), 502, code='NEON_API_ERROR')

    sentry_env = Config.SENTRY_ENVIRONMENT.lower()
    ambiente_atual = 'producao' if sentry_env.startswith('prod') else 'dev'

    return success_response({
        'ambienteAtual': ambiente_atual,
        'ambientes': ambientes,
    })


@platform_routes.route('/sair', methods=['POST'])
@require_platform_access()
def sair_da_empresa():
    empresa_id = getattr(g, 'platform_view_empresa_id', None)
    if empresa_id is not None:
        try:
            LogService.info(
                acao='platform_exit_tenant',
                mensagem=f'Administrador da plataforma saiu da empresa {empresa_id}.',
                entidade='Empresa',
                entidade_id=empresa_id,
                metadados={'platformAdminUserId': g.current_user.id, 'empresaId': empresa_id},
                empresa_id=empresa_id,
                strict=True,
            )
        except Exception:
            return error_response('Falha ao registrar auditoria da plataforma.', 500, code='PLATFORM_AUDIT_FAILED')
    response = jsonify({'success': True, 'message': 'Voltou para a empresa padrão.', 'data': None})
    clear_platform_view_cookie(response)
    return response
