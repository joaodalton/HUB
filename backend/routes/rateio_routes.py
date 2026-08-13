# backend/routes/rateio_routes.py
from flask import Blueprint, request

from services.rateio_service import aplicar_rateio, list_historico, preview_rateio
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


@rateio_routes.route('/historico', methods=['GET'])
def historico():
    competencia = request.args.get('competencia')
    plant_id = request.args.get('plantId', type=int)
    uc_id = request.args.get('ucId', type=int)

    return success_response(list_historico(competencia, plant_id, uc_id))