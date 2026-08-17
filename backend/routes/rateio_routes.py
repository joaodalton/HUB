# backend/routes/rateio_routes.py
from flask import Blueprint, request

from services.rateio_service import aplicar_rateio, confirmar_selecao, funil_qualificacao, list_historico, preview_rateio
from utils.api_response import error_response, success_response


rateio_routes = Blueprint('rateio_routes', __name__, url_prefix='/api/v1/rateio')


@rateio_routes.route('/preview', methods=['GET'])
def preview():
    plant_id = request.args.get('plantId', type=int)
    return success_response(preview_rateio(plant_id))


@rateio_routes.route('/aplicar', methods=['POST'])
def aplicar():
    data = request.get_json(silent=True) or {}
    competencia = data.get('competencia', '')
    plant_id = data.get('plantId')

    if not competencia:
        return error_response('Competencia e obrigatoria (formato YYYY-MM).', 400)

    try:
        resultado = aplicar_rateio(competencia, plant_id)
    except ValueError as exc:
        return error_response(str(exc), 400)

    return success_response(resultado, 'Rateio aplicado.')


@rateio_routes.route('/confirmar', methods=['POST'])
def confirmar():
    data = request.get_json(silent=True) or {}
    plant_id = data.get('plantId')
    competencia = data.get('competencia', '')
    selecoes = data.get('selecoes', [])

    if not plant_id:
        return error_response('plantId e obrigatorio.', 400)
    if not competencia:
        return error_response('Competencia e obrigatoria (formato YYYY-MM).', 400)

    try:
        resultado = confirmar_selecao(plant_id, competencia, selecoes)
    except ValueError as exc:
        return error_response(str(exc), 400)

    return success_response(resultado, 'Rateio confirmado. Clientes conectados a usina.', 201)


@rateio_routes.route('/qualificacao', methods=['GET'])
def qualificacao():
    plant_id = request.args.get('plantId', type=int)

    if not plant_id:
        return error_response('plantId e obrigatorio.', 400)

    try:
        return success_response(funil_qualificacao(plant_id))
    except ValueError as exc:
        return error_response(str(exc), 404)


@rateio_routes.route('/historico', methods=['GET'])
def historico():
    competencia = request.args.get('competencia')
    plant_id = request.args.get('plantId', type=int)
    uc_id = request.args.get('ucId', type=int)

    return success_response(list_historico(competencia, plant_id, uc_id))