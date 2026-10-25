from io import BytesIO

from flask import Blueprint, g, request, send_file

from extensions import limiter
from services.google_reports_auth import ReportAccountMissingError, ReportScopeError
from services.permission_service import require_permission
from services.reports_service import gerar_relatorio, gerar_relatorio_arquivo
from utils.api_response import error_response, success_response

report_routes = Blueprint('report_routes', __name__, url_prefix='/api/v1/reports')

_FORMATOS_ARQUIVO = {'docx', 'xlsx', 'pptx'}

_TIPOS = [
    {'tipo': 'cadastro', 'label': 'Cadastro'},
    {'tipo': 'financeiro', 'label': 'Financeiro'},
    {'tipo': 'rateio', 'label': 'Rateio'},
    {'tipo': 'producao', 'label': 'Estimativa de Produção'},
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
    tipo = body.get('tipo', '')
    formato = body.get('formato', '')
    competencia = body.get('competencia')

    if formato in _FORMATOS_ARQUIVO:
        try:
            dados, filename, mimetype = gerar_relatorio_arquivo(
                empresa_id=g.current_empresa_id, tipo=tipo, formato=formato, competencia=competencia,
            )
        except ValueError as exc:
            return error_response(str(exc), 400)
        return send_file(BytesIO(dados), mimetype=mimetype, as_attachment=True, download_name=filename)

    try:
        resultado = gerar_relatorio(
            empresa_id=g.current_empresa_id, tipo=tipo, formato=formato, competencia=competencia,
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
