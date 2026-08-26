# backend/routes/bulk_import_export_routes.py
"""
Rotes de importacao/exportacao em massa (CSV) para clientes, UCs e usinas.
"""
from flask import Blueprint, Response, g, request
from utils.api_response import error_response, success_response
from services.bulk_import_export_service import (
    export_clients_csv,
    export_ucs_csv,
    export_plants_csv,
    import_clients_from_csv,
    import_ucs_from_csv,
    import_plants_from_csv,
)

bulk_routes = Blueprint('bulk_routes', __name__, url_prefix='/api/v1/bulk')


def _csv_response(content, filename):
    resp = Response(content, mimetype='text/csv; charset=utf-8')
    resp.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp


@bulk_routes.route('/clients/export', methods=['GET'])
def export_clients():
    return _csv_response(export_clients_csv(g.current_empresa_id), 'clientes.csv')


@bulk_routes.route('/ucs/export', methods=['GET'])
def export_ucs():
    return _csv_response(export_ucs_csv(g.current_empresa_id), 'ucs.csv')


@bulk_routes.route('/plants/export', methods=['GET'])
def export_plants():
    return _csv_response(export_plants_csv(g.current_empresa_id), 'usinas.csv')


@bulk_routes.route('/clients/import', methods=['POST'])
def import_clients():
    text = request.get_data(as_text=True)
    if not text.strip():
        return error_response('CSV vazio.', 400)
    try:
        result = import_clients_from_csv(g.current_empresa_id, text)
    except Exception as exc:
        return error_response(f'Erro na importacao: {exc}', 400)
    msg = f'{result["importados"]} cliente(s) importado(s)'
    if result['falhas']:
        msg += f', {len(result["falhas"])} falha(s)'
    return success_response(result, msg)


@bulk_routes.route('/ucs/import', methods=['POST'])
def import_ucs():
    text = request.get_data(as_text=True)
    if not text.strip():
        return error_response('CSV vazio.', 400)
    try:
        result = import_ucs_from_csv(g.current_empresa_id, text)
    except Exception as exc:
        return error_response(f'Erro na importacao: {exc}', 400)
    msg = f'{result["importados"]} UC(s) importada(s)'
    if result['falhas']:
        msg += f', {len(result["falhas"])} falha(s)'
    return success_response(result, msg)


@bulk_routes.route('/plants/import', methods=['POST'])
def import_plants():
    text = request.get_data(as_text=True)
    if not text.strip():
        return error_response('CSV vazio.', 400)
    try:
        result = import_plants_from_csv(g.current_empresa_id, text)
    except Exception as exc:
        return error_response(f'Erro na importacao: {exc}', 400)
    msg = f'{result["importados"]} usina(s) importada(s)'
    if result['falhas']:
        msg += f', {len(result["falhas"])} falha(s)'
    return success_response(result, msg)
