from flask import Blueprint, g, request

from extensions import limiter
from services.google_reports_auth import ReportAccountMissingError, ReportScopeError
from services.permission_service import require_permission
from services.reports_service import gerar_relatorio
from utils.api_response import error_response, success_response

report_routes = Blueprint('report_routes', __name__, url_prefix='/api/v1/reports')

_TIPOS = [
    {'tipo': 'cadastro', 'label': 'Cadastro'},
    {'tipo': 'financeiro', 'label': 'Financeiro'},
    {'tipo': 'rateio', 'label': 'Rateio'},
]


@report_routes.get('/tipos')
@require_permission('reports.read')
def tipos():
    return success_response(_TIPOS)


@report_routes.post('/gerar')
@require_permission('reports.read')
@limiter.limit('10 per minute')
def gerar():
    body = request.get_json(silent=True) or {}
    try:
        resultado = gerar_relatorio(
            empresa_id=g.current_empresa_id,
            tipo=body.get('tipo', ''),
            formato=body.get('formato', ''),
            competencia=body.get('competencia'),
        )
    except ValueError as exc:
        return error_response(str(exc), 400)
    except ReportAccountMissingError as exc:
        return error_response(str(exc), 404, code='GOOGLE_ACCOUNT_MISSING')
    except ReportScopeError as exc:
        return error_response(
            str(exc), 409, code='GOOGLE_SCOPE_MISSING', details={'missingScopes': exc.missing_scopes}
        )
    return success_response(resultado, 'Relatorio gerado.', 201)
