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
from models.empresa import Empresa
from models.user import User
from services.log_service import LogService
from services.permission_service import require_platform_admin
from utils.api_response import error_response, success_response
from utils.auth import clear_platform_view_cookie, set_platform_view_cookie


platform_routes = Blueprint('platform_routes', __name__, url_prefix='/api/v1/platform')


@platform_routes.route('', methods=['GET'])
@require_platform_admin()
def overview():
    return success_response({
        'totalEmpresas': db.session.query(func.count(Empresa.id)).scalar() or 0,
        'totalUsuarios': db.session.query(func.count(User.id)).scalar() or 0,
    })


@platform_routes.route('/empresas', methods=['GET'])
@require_platform_admin()
def listar_empresas():
    rows = (
        db.session.query(Empresa, func.count(User.id).label('total_usuarios'))
        .outerjoin(User, User.empresa_id == Empresa.id)
        .group_by(Empresa.id)
        .order_by(Empresa.nome)
        .all()
    )
    return success_response([{
        'id': empresa.id,
        'nome': empresa.nome,
        'slug': empresa.slug,
        'status': empresa.status,
        'totalUsuarios': total_usuarios,
        'createdAt': empresa.created_at.isoformat() if empresa.created_at else None,
    } for empresa, total_usuarios in rows])


@platform_routes.route('/empresas/<int:empresa_id>/entrar', methods=['POST'])
@require_platform_admin()
def entrar_na_empresa(empresa_id: int):
    empresa = db.session.get(Empresa, empresa_id)

    if not empresa:
        return error_response('Empresa nao encontrada.', 404)

    response = jsonify({
        'success': True,
        'message': f'Visualizando "{empresa.nome}".',
        'data': {
            'id': empresa.id,
            'nome': empresa.nome,
            'status': empresa.status,
        },
    })
    g.current_empresa_id = empresa.id
    LogService.info(
        acao='platform_enter_tenant',
        mensagem=f'Administrador da plataforma entrou na empresa {empresa.id}.',
        entidade='Empresa',
        entidade_id=empresa.id,
        metadados={'platformAdminUserId': g.current_user.id, 'empresaId': empresa.id},
    )
    set_platform_view_cookie(response, empresa.id)
    return response


@platform_routes.route('/sair', methods=['POST'])
@require_platform_admin()
def sair_da_empresa():
    empresa_id = getattr(g, 'platform_view_empresa_id', None)
    if empresa_id is not None:
        LogService.info(
            acao='platform_exit_tenant',
            mensagem=f'Administrador da plataforma saiu da empresa {empresa_id}.',
            entidade='Empresa',
            entidade_id=empresa_id,
            metadados={'platformAdminUserId': g.current_user.id, 'empresaId': empresa_id},
        )
    response = jsonify({'success': True, 'message': 'Voltou para a empresa padrão.', 'data': None})
    clear_platform_view_cookie(response)
    return response
