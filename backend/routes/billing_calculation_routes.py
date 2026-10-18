"""Consulta e execução auditável do cálculo de cobrança C5.5."""
from io import BytesIO

from flask import Blueprint, g, jsonify, request, send_file
from sqlalchemy import and_, exists, or_, select
from sqlalchemy.orm import selectinload

from extensions import db
from models.calculo_cobranca import BillingCalculationExecution, BillingCalculationSnapshot
from models.client import Client
from models.consumer_unit import ConsumerUnit, PlantConnection
from models.empresa import Empresa
from models.fatura import Fatura
from models.fatura_concessionaria import FaturaConcessionaria
from models.pendencia import Pendencia
from services.billing_calculation_service import BillingCalculationService
from services.invoice_document_service import load_invoice_pdf
from services.object_storage import ObjectStorageError
from services.permission_service import require_permission
from utils.api_response import error_response, success_response


billing_calculation_routes = Blueprint('billing_calculation_routes', __name__,
    url_prefix='/api/v1/billing-calculations')
platform_billing_calculation_routes = Blueprint('platform_billing_calculation_routes', __name__,
    url_prefix='/api/v1/platform/empresas/<int:empresa_id>/billing-calculations')


@billing_calculation_routes.before_request
def _require_tenant_user():
    if request.method == 'OPTIONS':
        return None
    if getattr(g, 'current_user', None) is not None and g.current_user.is_platform_admin:
        return error_response('Selecione explicitamente a empresa no diagnóstico da plataforma.', 403)


def _execution(row, *, detail=False):
    stages = row.auditoria.get('stages', [])
    blocked = next((stage for stage in stages if stage['status'] in
                    ('REVIEW_REQUIRED', 'MISSING_DATA', 'UNSUPPORTED', 'ERROR')), None)
    result = {
        'id': row.id, 'empresaId': row.empresa_id,
        'invoiceId': row.fatura_concessionaria_id, 'snapshotId': row.snapshot_id,
        'status': row.status, 'createdAt': row.created_at.isoformat(),
        'durationMs': row.auditoria.get('duration_ms'),
        'blockedStage': blocked['stage'] if blocked else None,
        'blockers': blocked['blockers'] if blocked else [],
        'reused': next((stage['outputs'].get('reused') for stage in stages
                        if stage['stage'] == 'SNAPSHOT'), None),
    }
    if detail:
        result['auditoria'] = row.auditoria
    return result


def _snapshot(row):
    return {
        'id': row.id, 'empresaId': row.empresa_id,
        'invoiceId': row.fatura_concessionaria_id, 'fingerprint': row.fingerprint,
        'regraSnapshot': row.regra_snapshot, 'entradaNormalizada': row.entrada_normalizada,
        'resultado': row.resultado, 'valorFinal': str(row.valor_final),
        'createdAt': row.created_at.isoformat(),
    }


def _invoices():
    def positive_int(name, default, maximum=None):
        raw = request.args.get(name)
        if raw is None:
            return default
        if not raw.isdigit() or int(raw) < 1 or (maximum and int(raw) > maximum):
            raise ValueError(name)
        return int(raw)

    try:
        page = positive_int('page', 1)
        page_size = positive_int('pageSize', 50, 100)
        usina_id = positive_int('usinaId', None)
    except ValueError as exc:
        return error_response(f'Filtro {exc} invalido.', 400, code='INVALID_INVOICE_FILTER')

    tenant = g.current_empresa_id
    invoice = FaturaConcessionaria
    pending = exists(select(Pendencia.id).where(
        Pendencia.empresa_id == tenant,
        Pendencia.fatura_concessionaria_id == invoice.id,
        Pendencia.status == 'aberta',
    ))
    charge_match = and_(
        Fatura.empresa_id == tenant,
        Fatura.consumer_unit_id == invoice.consumer_unit_id,
        Fatura.competencia == invoice.competencia,
    )
    query = invoice.query.filter(invoice.empresa_id == tenant)
    search = request.args.get('q', '').strip()
    if search:
        pattern = f'%{search}%'
        query = query.join(Client, and_(Client.id == invoice.client_id, Client.empresa_id == tenant))
        query = query.outerjoin(ConsumerUnit, and_(ConsumerUnit.id == invoice.consumer_unit_id,
                                                   ConsumerUnit.empresa_id == tenant))
        query = query.filter(or_(Client.nome.ilike(pattern), ConsumerUnit.codigo.ilike(pattern),
                                 invoice.codigo_uc_extraido.ilike(pattern)))
    if usina_id is not None:
        query = query.filter(exists(select(PlantConnection.id).where(
            PlantConnection.empresa_id == tenant,
            PlantConnection.consumer_unit_id == invoice.consumer_unit_id,
            PlantConnection.plant_id == usina_id,
        )))
    if request.args.get('competencia'):
        query = query.filter(invoice.competencia == request.args['competencia'])
    if request.args.get('statusProcessamento'):
        status = request.args['statusProcessamento']
        query = query.filter(or_(invoice.status_extracao == status, invoice.status_validacao == status))
    charge_status = request.args.get('statusCobranca')
    if charge_status:
        if charge_status == 'sem_cobranca':
            query = query.filter(~exists(select(Fatura.id).where(charge_match)))
        else:
            query = query.filter(exists(select(Fatura.id).where(
                charge_match, Fatura.asaas_status == charge_status)))
    pending_filter = request.args.get('comPendencia')
    if pending_filter in ('true', 'false'):
        query = query.filter(pending if pending_filter == 'true' else ~pending)
    elif pending_filter is not None:
        return error_response('Filtro comPendencia invalido.', 400, code='INVALID_INVOICE_FILTER')

    total = query.count()
    rows = query.options(
        selectinload(invoice.client), selectinload(invoice.document),
        selectinload(invoice.consumer_unit).selectinload(ConsumerUnit.conexoes).selectinload(PlantConnection.plant),
    ).order_by(invoice.created_at.desc(), invoice.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    contexts = {(row.consumer_unit_id, row.competencia) for row in rows
                if row.consumer_unit_id is not None and row.competencia is not None}
    charges_by_context = {}
    if contexts:
        charges = Fatura.query.filter(Fatura.empresa_id == tenant, or_(*(
            and_(Fatura.consumer_unit_id == uc_id, Fatura.competencia == competencia)
            for uc_id, competencia in contexts))).order_by(Fatura.created_at.desc(), Fatura.id.desc()).all()
        for charge in charges:
            charges_by_context.setdefault((charge.consumer_unit_id, charge.competencia), []).append({
                'id': charge.id, 'statusInterno': charge.status_interno,
                'asaasStatus': charge.asaas_status, 'asaasId': charge.asaas_id,
                'valor': float(charge.valor), 'mesVencimento': charge.mes_vencimento.isoformat(),
                'boletoUrl': charge.boleto_url,
            })
    pending_ids = {row.fatura_concessionaria_id for row in Pendencia.query.filter(
        Pendencia.empresa_id == tenant, Pendencia.status == 'aberta',
        Pendencia.fatura_concessionaria_id.in_([row.id for row in rows])).all()}
    data = [{
        'id': row.id, 'clientId': row.client_id, 'clienteNome': row.client.nome if row.client else None,
        'consumerUnitId': row.consumer_unit_id,
        'ucCodigo': row.consumer_unit.codigo if row.consumer_unit else row.codigo_uc_extraido,
        'usinas': [{'id': link.plant_id, 'nome': link.plant.nome} for link in row.consumer_unit.conexoes
                   if link.empresa_id == tenant and link.plant and link.plant.empresa_id == tenant]
                  if row.consumer_unit else [],
        'competencia': row.competencia, 'statusExtracao': row.status_extracao,
        'statusValidacao': row.status_validacao,
        'valorTotalConcessionaria': str(row.valor_total_concessionaria)
        if row.valor_total_concessionaria is not None else None,
        'dataVencimento': row.data_vencimento.isoformat() if row.data_vencimento else None,
        'documentoId': row.document_id,
        'documentoDisponivel': bool(row.document and row.document.empresa_id == tenant
                                    and row.document.client_id == row.client_id
                                    and row.document.storage_provider in ('google_drive', 'local', 's3')
                                    and row.document.storage_ref),
        'temPendencia': row.id in pending_ids,
        'contextualCharges': charges_by_context.get((row.consumer_unit_id, row.competencia), []),
        'createdAt': row.created_at.isoformat(),
    } for row in rows]
    return jsonify({'success': True, 'message': 'OK', 'data': data,
                    'pagination': {'page': page, 'pageSize': page_size, 'total': total,
                                   'pages': (total + page_size - 1) // page_size}})


def _list():
    query = BillingCalculationExecution.query.filter_by(empresa_id=g.current_empresa_id)
    invoice_id = request.args.get('invoiceId')
    if invoice_id is not None:
        if not invoice_id.isdigit() or int(invoice_id) <= 0:
            return error_response('Fatura inválida.', 400, code='INVALID_INVOICE_ID')
        query = query.filter_by(fatura_concessionaria_id=int(invoice_id))
    rows = query.order_by(BillingCalculationExecution.created_at.desc(),
                          BillingCalculationExecution.id.desc()).limit(100).all()
    return success_response([_execution(row) for row in rows])


def _execute(invoice_id):
    try:
        execution = BillingCalculationService().execute(invoice_id)
    except LookupError:
        return error_response('Fatura não encontrada.', 404)
    return success_response(_execution(execution, detail=True), 'Cálculo executado.', 201)


def _download_invoice(invoice_id):
    try:
        result = load_invoice_pdf(invoice_id, g.current_empresa_id)
    except ObjectStorageError:
        return error_response('Armazenamento de documentos indisponivel.', 503,
                              code='DOCUMENT_STORAGE_UNAVAILABLE')
    if result is None:
        return error_response('Fatura não encontrada.', 404)
    data, filename = result
    return send_file(BytesIO(data), mimetype='application/pdf', as_attachment=True,
                     download_name=filename)


def _detail(execution_id):
    row = BillingCalculationExecution.query.filter_by(
        id=execution_id, empresa_id=g.current_empresa_id).first()
    return success_response(_execution(row, detail=True)) if row else error_response('Execução não encontrada.', 404)


def _snapshot_detail(snapshot_id):
    row = BillingCalculationSnapshot.query.filter_by(
        id=snapshot_id, empresa_id=g.current_empresa_id).first()
    return success_response(_snapshot(row)) if row else error_response('Snapshot não encontrado.', 404)


@billing_calculation_routes.get('/invoices')
@require_permission('billing_calculations.read')
def invoices():
    return _invoices()


@billing_calculation_routes.get('/invoices/<int:invoice_id>/download')
@require_permission('faturas.read')
def download_invoice(invoice_id):
    return _download_invoice(invoice_id)


@billing_calculation_routes.post('/invoices/upload')
def upload_invoice_without_client():
    from routes.client_routes import upload_concessionaria_invoice
    return upload_concessionaria_invoice(None)


@billing_calculation_routes.get('')
@require_permission('billing_calculations.read')
def index():
    return _list()


@billing_calculation_routes.post('/invoices/<int:invoice_id>/execute')
@require_permission('billing_calculations.execute')
def execute(invoice_id):
    return _execute(invoice_id)


@billing_calculation_routes.get('/executions/<int:execution_id>')
@require_permission('billing_calculations.read')
def detail(execution_id):
    return _detail(execution_id)


@billing_calculation_routes.get('/snapshots/<int:snapshot_id>')
@require_permission('billing_calculations.read')
def snapshot_detail(snapshot_id):
    return _snapshot_detail(snapshot_id)


@platform_billing_calculation_routes.before_request
def _require_selected_company():
    if request.method == 'OPTIONS':
        return None
    user = getattr(g, 'current_user', None)
    if user is None:
        return error_response('Autenticação obrigatória.', 401)
    if not user.is_platform_admin:
        return error_response('Acesso restrito a administradores da plataforma.', 403)
    empresa_id = request.view_args['empresa_id']
    if db.session.get(Empresa, empresa_id) is None:
        return error_response('Empresa não encontrada.', 404)
    g.current_empresa_id = empresa_id


@platform_billing_calculation_routes.get('/clients')
def platform_clients(empresa_id):
    rows = Client.query.filter_by(empresa_id=empresa_id).order_by(Client.nome, Client.id).limit(100).all()
    return success_response([{'id': row.id, 'nome': row.nome} for row in rows])


@platform_billing_calculation_routes.post('/clients/<int:client_id>/invoices/upload')
def platform_upload(empresa_id, client_id):
    from routes.client_routes import upload_concessionaria_invoice
    return upload_concessionaria_invoice(client_id)


@platform_billing_calculation_routes.get('/invoices')
def platform_invoices(empresa_id):
    return _invoices()


@platform_billing_calculation_routes.get('/invoices/<int:invoice_id>/download')
@require_permission('faturas.read')
def platform_download_invoice(empresa_id, invoice_id):
    return _download_invoice(invoice_id)


@platform_billing_calculation_routes.post('/invoices/upload')
def platform_upload_without_client(empresa_id):
    from routes.client_routes import upload_concessionaria_invoice
    return upload_concessionaria_invoice(None)


@platform_billing_calculation_routes.get('')
def platform_index(empresa_id):
    return _list()


@platform_billing_calculation_routes.post('/invoices/<int:invoice_id>/execute')
def platform_execute(empresa_id, invoice_id):
    return _execute(invoice_id)


@platform_billing_calculation_routes.get('/executions/<int:execution_id>')
def platform_detail(empresa_id, execution_id):
    return _detail(execution_id)


@platform_billing_calculation_routes.get('/snapshots/<int:snapshot_id>')
def platform_snapshot_detail(empresa_id, snapshot_id):
    return _snapshot_detail(snapshot_id)
