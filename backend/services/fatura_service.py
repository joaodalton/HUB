from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
from uuid import uuid4

from flask import g
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from extensions import db
from models.client import Client
from models.consumer_unit import ConsumerUnit
from models.fatura import Fatura
from models.user import User
from services.asaas_client import AsaasClient, AsaasError, customer_payload, payment_payload
from services.log_service import LogService
from services.permission_service import can


STATUS_MAP = {'PENDING': 'pending', 'RECEIVED': 'received', 'CONFIRMED': 'received', 'OVERDUE': 'overdue', 'CANCELLED': 'canceled', 'DELETED': 'canceled', 'REFUNDED': 'refunded'}


class EmissaoPendente(AsaasError):
    def __init__(self, fatura_id):
        super().__init__('Emissao pendente de conciliacao. Repita o mesmo comando; nao crie outra cobranca.')
        self.fatura_id = fatura_id


def _autorizar_emissao(empresa_id, user_id):
    user = User.query.filter_by(id=user_id, status='ativo').first()
    tenant = getattr(g, 'current_empresa_id', None)
    actor = getattr(g, 'current_user', None)
    platform_view = (user and user.is_platform_admin and tenant == empresa_id
                     and getattr(getattr(g, 'current_user', None), 'id', None) == user_id)
    if (not user or not can(user, 'faturas.create')
            or (user.empresa_id != empresa_id and not platform_view)
            or (actor is not None and actor.id != user_id)
            or (tenant is not None and tenant != empresa_id)):
        raise PermissionError('Sem permissao para emitir nesta empresa.')


def _client(client_id: int, empresa_id: int):
    return Client.query.filter_by(id=client_id, empresa_id=empresa_id).first()


def _uc(uc_id: int, empresa_id: int):
    return ConsumerUnit.query.filter_by(id=uc_id, empresa_id=empresa_id).first()


def emitir(data: dict, empresa_id: int, user_id: int) -> dict:
    _autorizar_emissao(empresa_id, user_id)
    if not isinstance(data, dict):
        raise ValueError('Payload invalido.')
    if any(type(data.get(key)) is not int or data[key] <= 0 for key in ('clienteId', 'ucId')):
        raise ValueError('Cliente e UC devem ser identificadores inteiros positivos.')
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
    if (not valor.is_finite() or not 0 < valor <= Decimal('99999999.99')
            or not isinstance(competencia, str)
            or not re.fullmatch(r'[0-9]{4}-(0[1-9]|1[0-2])', competencia)
            or competencia.startswith('0000')):
        raise ValueError('Informe valor positivo e competência no formato YYYY-MM.')
    key = hashlib.sha256(json.dumps([
        empresa_id, client.id, uc.id, competencia, str(valor), vencimento.isoformat(),
    ], separators=(',', ':')).encode()).hexdigest()
    fatura = Fatura.query.filter_by(empresa_id=empresa_id, emission_key=key).first()
    if not fatura:
        fatura = Fatura(empresa_id=empresa_id, client_id=client.id, consumer_unit_id=uc.id,
                       concessionaria=uc.concessionaria or client.concessionaria,
                       competencia=competencia, valor=valor, mes_vencimento=vencimento,
                       origem='manual', criado_por_id=user_id, status_interno='aguardando_emissao',
                       payment_provider='asaas', external_reference=f'hub-{uuid4().hex}', emission_key=key)
        db.session.add(fatura)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            fatura = Fatura.query.filter_by(empresa_id=empresa_id, emission_key=key).first()
            if not fatura:
                raise
    if fatura.asaas_id:
        return fatura.to_dict()
    asaas = AsaasClient(empresa_id)
    fatura_id = fatura.id
    # CAS persistido: só o vencedor pode fazer efeitos externos. Não expira por tempo.
    claimed = Fatura.query.filter_by(id=fatura_id, empresa_id=empresa_id,
        emissao_iniciada_em=None, asaas_id=None).update({
            Fatura.emissao_iniciada_em: datetime.utcnow(),
            Fatura.status_interno: 'aguardando_emissao',
        }, synchronize_session=False)
    db.session.commit()
    db.session.refresh(fatura)
    if not claimed:
        return _reconciliar(fatura, asaas)
    try:
        if not client.asaas_customer_id:
            customer = asaas.criar_cliente(customer_payload(client))
            if not isinstance(customer.get('id'), str) or not customer['id']:
                raise AsaasError('Resposta de cliente ASAAS invalida.')
            client.asaas_customer_id = customer['id']
        fatura.payment_customer_id = client.asaas_customer_id
        db.session.commit()
    except AsaasError:
        # Prova local: /payments ainda NÃO foi invocado; pode liberar nova tentativa.
        db.session.rollback()
        fatura.emissao_iniciada_em = None
        fatura.status_interno = 'erro_emissao'
        db.session.commit()
        raise
    try:
        payment = asaas.criar_cobranca(payment_payload(
            fatura.payment_customer_id, fatura.valor, fatura.mes_vencimento, fatura.external_reference))
        return _concluir_emissao(fatura, payment)
    except AsaasError:
        db.session.rollback()
        # O POST pode ter sido aceito. Nunca liberar a reserva, nem após HTTP 4xx/5xx.
        Fatura.query.filter_by(id=fatura_id, empresa_id=empresa_id, asaas_id=None).update(
            {Fatura.status_interno: 'erro_emissao'}, synchronize_session=False)
        db.session.commit()
        db.session.refresh(fatura)
        return _reconciliar(fatura, asaas)
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise EmissaoPendente(fatura_id) from exc


def _reconciliar(fatura, asaas):
    if fatura.asaas_id:
        return fatura.to_dict()
    if not fatura.external_reference:
        raise EmissaoPendente(fatura.id)
    payment = asaas.consultar_por_referencia(fatura.external_reference)
    if payment is None:
        # Ausência na listagem não prova que um POST em voo não será efetivado.
        raise EmissaoPendente(fatura.id)
    fatura_id = fatura.id
    try:
        return _concluir_emissao(fatura, payment)
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise EmissaoPendente(fatura_id) from exc


def _concluir_emissao(fatura, payment):
    try:
        valid = (isinstance(payment.get('id'), str) and bool(payment['id'])
                 and payment.get('externalReference') == fatura.external_reference
                 and payment.get('customer') == fatura.payment_customer_id
                 and payment.get('billingType') == 'BOLETO'
                 and Decimal(str(payment.get('value'))) == fatura.valor
                 and payment.get('dueDate') == fatura.mes_vencimento.isoformat()
                 and payment.get('status') in STATUS_MAP)
    except InvalidOperation:
        valid = False
    if not valid or (fatura.asaas_id and fatura.asaas_id != payment['id']):
        raise AsaasError('Cobranca ASAAS divergente da intencao local; conciliacao manual necessaria.')
    fatura.asaas_id = payment['id']
    _apply_payment(fatura, payment)
    fatura.status_interno = 'cancelada' if fatura.asaas_status == 'canceled' else 'emitida'
    db.session.commit()
    LogService.info(acao='fatura_emitida', mensagem='Fatura emitida/conciliada via ASAAS.',
                    entidade='Fatura', entidade_id=fatura.id, metadados={'faturaId': fatura.id})
    return fatura.to_dict()


def listar(empresa_id: int, filtros: dict) -> list[dict]:
    query = Fatura.query.filter_by(empresa_id=empresa_id)
    for field, column in [('clienteId', Fatura.client_id), ('ucId', Fatura.consumer_unit_id), ('status', Fatura.asaas_status), ('competencia', Fatura.competencia)]:
        if filtros.get(field): query = query.filter(column == filtros[field])
    return [item.to_dict() for item in query.order_by(Fatura.created_at.desc()).all()]


def obter(fatura_id: int, empresa_id: int):
    return Fatura.query.filter_by(id=fatura_id, empresa_id=empresa_id).first()


def sincronizar(fatura: Fatura) -> dict:
    if not fatura.asaas_id:
        return _reconciliar(fatura, AsaasClient(fatura.empresa_id))
    payment = AsaasClient(fatura.empresa_id).consultar_cobranca(fatura.asaas_id)
    if fatura.status_interno is not None:
        fatura.status_interno = 'cancelada' if payment.get('status') in ('CANCELLED', 'DELETED') else 'emitida'
    _apply_payment(fatura, payment); db.session.commit()
    return fatura.to_dict()


def cancelar(fatura: Fatura) -> dict:
    if not fatura.asaas_id:
        raise EmissaoPendente(fatura.id)
    payment = AsaasClient(fatura.empresa_id).cancelar_cobranca(fatura.asaas_id)
    if payment.get('deleted') is True:
        payment = {**payment, 'status': 'DELETED'}
    if fatura.status_interno is not None:
        fatura.status_interno = 'cancelada' if payment.get('status') in ('CANCELLED', 'DELETED') else 'emitida'
    _apply_payment(fatura, payment); db.session.commit()
    return fatura.to_dict()


def resumo(empresa_id: int) -> dict:
    rows = Fatura.query.filter_by(empresa_id=empresa_id).filter(Fatura.asaas_id.isnot(None)).all()
    return {status: sum(1 for row in rows if row.asaas_status == status) for status in ('pending', 'received', 'overdue', 'canceled')}


def _apply_payment(fatura: Fatura, payment: dict) -> None:
    fatura.asaas_status = STATUS_MAP.get(payment.get('status', '').upper(), 'pending')
    fatura.boleto_url = payment.get('bankSlipUrl') or payment.get('invoiceUrl')
    fatura.linha_digitavel = payment.get('identificationField')
    fatura.codigo_barras = payment.get('nossoNumero')
