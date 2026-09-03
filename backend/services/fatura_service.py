from datetime import date
from decimal import Decimal, InvalidOperation

from extensions import db
from models.client import Client
from models.consumer_unit import ConsumerUnit
from models.fatura import Fatura
from services.asaas_client import AsaasClient, AsaasError, customer_payload, payment_payload
from services.log_service import LogService


STATUS_MAP = {'PENDING': 'pending', 'RECEIVED': 'received', 'CONFIRMED': 'received', 'OVERDUE': 'overdue', 'CANCELLED': 'canceled', 'DELETED': 'canceled', 'REFUNDED': 'refunded'}


def _client(client_id: int, empresa_id: int):
    return Client.query.filter_by(id=client_id, empresa_id=empresa_id).first()


def _uc(uc_id: int, empresa_id: int):
    return ConsumerUnit.query.filter_by(id=uc_id, empresa_id=empresa_id).first()


def emitir(data: dict, empresa_id: int, user_id: int) -> dict:
    client = _client(data.get('clienteId'), empresa_id)
    uc = _uc(data.get('ucId'), empresa_id)
    if not client or not uc or uc.client_id != client.id:
        raise ValueError('Cliente ou UC não encontrado.')
    try:
        valor = Decimal(str(data.get('valor'))).quantize(Decimal('0.01'))
        vencimento = date.fromisoformat(data.get('mesVencimento', ''))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError('Valor ou vencimento inválido.')
    competencia = data.get('competencia', '')
    if valor <= 0 or len(competencia) != 7:
        raise ValueError('Informe valor positivo e competência no formato YYYY-MM.')

    asaas = AsaasClient(empresa_id)
    if not client.asaas_customer_id:
        customer = asaas.criar_cliente(customer_payload(client))
        client.asaas_customer_id = customer['id']
        db.session.flush()
    payment = asaas.criar_cobranca(payment_payload(client.asaas_customer_id, valor, vencimento, f'hub-{empresa_id}-{uc.id}-{competencia}'))
    fatura = Fatura(empresa_id=empresa_id, client_id=client.id, consumer_unit_id=uc.id, concessionaria=uc.concessionaria or client.concessionaria, competencia=competencia, valor=valor, mes_vencimento=vencimento, origem='manual', criado_por_id=user_id, asaas_id=payment['id'])
    _apply_payment(fatura, payment)
    db.session.add(fatura)
    db.session.commit()
    LogService.info(acao='fatura_emitida', mensagem='Fatura emitida via ASAAS.', entidade='Fatura', entidade_id=fatura.id, metadados={'faturaId': fatura.id})
    return fatura.to_dict()


def listar(empresa_id: int, filtros: dict) -> list[dict]:
    query = Fatura.query.filter_by(empresa_id=empresa_id)
    for field, column in [('clienteId', Fatura.client_id), ('ucId', Fatura.consumer_unit_id), ('status', Fatura.asaas_status), ('competencia', Fatura.competencia)]:
        if filtros.get(field): query = query.filter(column == filtros[field])
    return [item.to_dict() for item in query.order_by(Fatura.created_at.desc()).all()]


def obter(fatura_id: int, empresa_id: int):
    return Fatura.query.filter_by(id=fatura_id, empresa_id=empresa_id).first()


def sincronizar(fatura: Fatura) -> dict:
    payment = AsaasClient(fatura.empresa_id).consultar_cobranca(fatura.asaas_id)
    _apply_payment(fatura, payment); db.session.commit()
    return fatura.to_dict()


def cancelar(fatura: Fatura) -> dict:
    payment = AsaasClient(fatura.empresa_id).cancelar_cobranca(fatura.asaas_id)
    _apply_payment(fatura, payment); db.session.commit()
    return fatura.to_dict()


def processar_webhook(payment: dict) -> bool:
    fatura = Fatura.query.filter_by(asaas_id=payment.get('id')).first()
    if not fatura: return False
    _apply_payment(fatura, payment); db.session.commit()
    return True


def resumo(empresa_id: int) -> dict:
    rows = Fatura.query.filter_by(empresa_id=empresa_id).all()
    return {status: sum(1 for row in rows if row.asaas_status == status) for status in ('pending', 'received', 'overdue', 'canceled')}


def _apply_payment(fatura: Fatura, payment: dict) -> None:
    fatura.asaas_status = STATUS_MAP.get(payment.get('status', '').upper(), 'pending')
    fatura.boleto_url = payment.get('bankSlipUrl') or payment.get('invoiceUrl')
    fatura.linha_digitavel = payment.get('identificationField')
    fatura.codigo_barras = payment.get('nossoNumero')
