from io import BytesIO

from flask import Blueprint, g, request, send_file

from extensions import limiter
from services.google_reports_auth import ReportAccountMissingError, ReportScopeError
from services.permission_service import require_permission
from services.report_template_service import create_template, delete_template, list_templates, update_template
from services.report_source_template_service import get_config as get_source_config, remove_source, set_drive_source, set_upload_source
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


@report_routes.get('/templates')
@require_permission('reports.read')
def templates():
    return success_response(list_templates(g.current_empresa_id))


@report_routes.post('/templates')
@require_permission('settings.update')
def criar_template():
    body = request.get_json(silent=True) or {}
    try:
        template = create_template(g.current_empresa_id, body.get('nome', ''), body.get('accentHex'))
    except ValueError as exc:
        return error_response(str(exc), 400)
    return success_response(template, 'Template criado.', 201)


@report_routes.put('/templates/<int:template_id>')
@require_permission('settings.update')
def atualizar_template(template_id: int):
    body = request.get_json(silent=True) or {}
    try:
        template = update_template(g.current_empresa_id, template_id, body)
    except ValueError as exc:
        return error_response(str(exc), 400)
    if not template:
        return error_response('Template nao encontrado.', 404)
    return success_response(template, 'Template atualizado.')


@report_routes.delete('/templates/<int:template_id>')
@require_permission('settings.update')
def excluir_template(template_id: int):
    if not delete_template(g.current_empresa_id, template_id):
        return error_response('Template nao encontrado.', 404)
    return success_response(None, 'Template excluido.')


@report_routes.get('/source-templates/<categoria>')
@require_permission('reports.read')
def obter_fonte(categoria: str):
    try:
        return success_response(get_source_config(categoria, g.current_empresa_id))
    except ValueError as exc:
        return error_response(str(exc), 400)


@report_routes.put('/source-templates/<categoria>/drive')
@require_permission('settings.update')
def configurar_fonte_drive(categoria: str):
    body = request.get_json(silent=True) or {}
    try:
        resultado = set_drive_source(categoria, g.current_empresa_id, body.get('driveFileId', ''))
    except ValueError as exc:
        return error_response(str(exc), 400)
    return success_response(resultado, 'Template configurado.')


@report_routes.post('/source-templates/<categoria>/upload')
@require_permission('settings.update')
def configurar_fonte_upload(categoria: str):
    try:
        resultado = set_upload_source(categoria, g.current_empresa_id, request.files.get('arquivo'))
    except ValueError as exc:
        return error_response(str(exc), 400)
    return success_response(resultado, 'Template configurado.')


@report_routes.delete('/source-templates/<categoria>')
@require_permission('settings.update')
def remover_fonte(categoria: str):
    try:
        remove_source(categoria)
    except ValueError as exc:
        return error_response(str(exc), 400)
    return success_response(None, 'Template removido.')


@report_routes.post('/gerar')
@require_permission('reports.read')
@limiter.limit('10 per minute')
def gerar():
    body = request.get_json(silent=True) or {}
    tipo = body.get('tipo', '')
    formato = body.get('formato', '')
    competencia = body.get('competencia')
    template_id = body.get('template')

    if formato in _FORMATOS_ARQUIVO:
        try:
            dados, filename, mimetype = gerar_relatorio_arquivo(
                empresa_id=g.current_empresa_id, tipo=tipo, formato=formato, competencia=competencia, template_id=template_id,
            )
        except ValueError as exc:
            return error_response(str(exc), 400)
        return send_file(BytesIO(dados), mimetype=mimetype, as_attachment=True, download_name=filename)

    try:
        resultado = gerar_relatorio(
            empresa_id=g.current_empresa_id, tipo=tipo, formato=formato, competencia=competencia, template_id=template_id,
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
