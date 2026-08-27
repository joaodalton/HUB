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

from models.empresa import Empresa
from services.permission_service import require_platform_admin
from utils.api_response import error_response, success_response
from utils.auth import clear_platform_view_cookie, set_platform_view_cookie


platform_routes = Blueprint('platform_routes', __name__, url_prefix='/api/v1/platform')


@platform_routes.route('/empresas', methods=['GET'])
@require_platform_admin()
def listar_empresas():
    empresas = Empresa.query.order_by(Empresa.nome).all()
    return success_response([empresa.to_dict() for empresa in empresas])


@platform_routes.route('/empresas/<int:empresa_id>/entrar', methods=['POST'])
@require_platform_admin()
def entrar_na_empresa(empresa_id: int):
    empresa = Empresa.query.get(empresa_id)

    if not empresa:
        return error_response('Empresa nao encontrada.', 404)

    response = jsonify({
        'success': True,
        'message': f'Visualizando "{empresa.nome}".',
        'data': empresa.to_dict()
    })
    set_platform_view_cookie(response, empresa.id)
    return response


@platform_routes.route('/sair', methods=['POST'])
@require_platform_admin()
def sair_da_empresa():
    response = jsonify({'success': True, 'message': 'Voltou para a empresa padrão.', 'data': None})
    clear_platform_view_cookie(response)
    return response