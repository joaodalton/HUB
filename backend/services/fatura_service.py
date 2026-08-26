# backend/services/fatura_service.py
"""
Regra de negócio de Faturas -- decide QUANDO e COMO usar o ASAAS
(integrations/asaas_client.py, que só sabe "conversar com a API"). Cria o
customer no ASAAS se ainda não existir (rastreado por externalReference =
'client-<id>'), cria a cobrança, e reage aos webhooks de pagamento.
"""
from datetime import date, datetime

from flask import g

from extensions import db
from integrations import asaas_client
from integrations.asaas_client import AsaasError
from models.client import Client
from models.consumer_unit import ConsumerUnit
from models.fatura import Fatura
from services.log_service import LogService


def list_faturas(filtros: dict) -> list[dict]:
    query = Fatura.query

    if filtros.get('clienteId'):
        query = query.filter(Fatura.client_id == filtros['clienteId'])
    if filtros.get('status'):
        query = query.filter(Fatura.status == filtros['status'])
    if filtros.get('competencia'):
        query = query.filter(Fatura.competencia == filtros['competencia'])

    faturas = query.order_by(Fatura.vencimento.desc()).all()
    return [fatura.to_dict() for fatura in faturas]


def get_fatura(fatura_id: int) -> dict | None:
    fatura = Fatura.query.get(fatura_id)
    return fatura.to_dict() if fatura else None


def criar_fatura(data: dict) -> dict:
    if not asaas_client.is_configured():
        raise ValueError('ASAAS não configurado -- defina ASAAS_API_KEY no .env antes de criar faturas.')

    client = Client.query.get(data.get('clienteId'))
    if not client:
        raise ValueError('Cliente informado não existe.')

    if not client.cpf:
        raise ValueError('Cliente precisa ter CPF cadastrado antes de gerar cobrança.')

    uc_id = data.get('ucId')
    if uc_id and not ConsumerUnit.query.get(uc_id):
        raise ValueError('UC informada não existe.')

    valor_cobrado = data.get('valorCobrado')
    if not valor_cobrado or float(valor_cobrado) <= 0:
        raise ValueError('Valor cobrado precisa ser maior que zero.')

    vencimento = _parse_date(data.get('vencimento'))
    if not vencimento:
        raise ValueError('Vencimento é obrigatório (formato YYYY-MM-DD).')

    competencia = (data.get('competencia') or '').strip()
    _validar_competencia(competencia)

    try:
        asaas_customer_id = _obter_ou_criar_customer(client)
    except AsaasError as exc:
        raise ValueError(f'Erro ao cadastrar cliente no ASAAS: {exc}')

    fatura = Fatura(
        empresa_id=g.current_empresa_id,
        client_id=client.id,
        consumer_unit_id=uc_id,
        competencia=competencia,
        valor_original=data.get('valorOriginal'),
        desconto_percentual=data.get('descontoPercentual'),
        valor_cobrado=valor_cobrado,
        vencimento=vencimento,
        status='pendente',
        asaas_customer_id=asaas_customer_id
    )
    db.session.add(fatura)
    db.session.flush()  # precisa do fatura.id antes de criar a cobrança (external_reference)

    try:
        cobranca = asaas_client.create_charge(
            customer_id=asaas_customer_id,
            value=float(valor_cobrado),
            due_date=vencimento.isoformat(),
            description=f'Fatura {competencia} — {client.nome}',
            billing_type=data.get('formaPagamento', 'BOLETO'),
            external_reference=f'fatura-{fatura.id}'
        )
    except AsaasError as exc:
        db.session.rollback()
        raise ValueError(f'Erro ao criar cobrança no ASAAS: {exc}')

    fatura.asaas_charge_id = cobranca.get('id')
    fatura.forma_pagamento = cobranca.get('billingType')
    fatura.link_pagamento = cobranca.get('invoiceUrl') or cobranca.get('bankSlipUrl')
    db.session.commit()

    LogService.info(
        acao='fatura_criada',
        mensagem=f'Fatura de {competencia} criada para {client.nome} (R$ {valor_cobrado})',
        entidade='Fatura',
        entidade_id=fatura.id,
        metadados={'asaasChargeId': fatura.asaas_charge_id}
    )
    return fatura.to_dict()


def cancelar_fatura(fatura_id: int) -> dict | None:
    fatura = Fatura.query.get(fatura_id)
    if not fatura:
        return None

    if fatura.asaas_charge_id:
        try:
            asaas_client.cancel_charge(fatura.asaas_charge_id)
        except AsaasError as exc:
            raise ValueError(f'Erro ao cancelar cobrança no ASAAS: {exc}')

    fatura.status = 'cancelado'
    db.session.commit()

    LogService.info(acao='fatura_cancelada', mensagem=f'Fatura {fatura.id} cancelada', entidade='Fatura', entidade_id=fatura.id)
    return fatura.to_dict()


def processar_webhook(payload: dict) -> None:
    """Chamado pela rota pública /faturas/webhook/asaas. Formato do payload:
    { "event": "PAYMENT_RECEIVED", "payment": { "id": "pay_xxx", ... } }
    Nunca lança exceção pra evento desconhecido/fatura não encontrada --
    só loga, pra sempre responder 200 pro ASAAS (senão ele fica reenviando)."""
    evento = payload.get('event', '')
    payment = payload.get('payment') or {}
    charge_id = payment.get('id')

    if not charge_id:
        LogService.warning(
            acao='asaas_webhook_invalido',
            mensagem='Webhook do ASAAS sem payment.id',
            entidade='Fatura',
            metadados={'payload': payload}
        )
        return

    fatura = Fatura.query.filter_by(asaas_charge_id=charge_id).first()
    if not fatura:
        LogService.warning(
            acao='asaas_webhook_fatura_nao_encontrada',
            mensagem=f'Webhook "{evento}" recebido pra cobrança {charge_id}, mas nenhuma Fatura corresponde.',
            entidade='Fatura',
            metadados={'charge_id': charge_id, 'evento': evento, 'payload': payload}
        )
        return

    novo_status = _mapear_status(evento)
    if not novo_status:
        LogService.info(
            acao='asaas_webhook_ignorado',
            mensagem=f'Evento "{evento}" não altera status de fatura',
            entidade='Fatura',
            entidade_id=fatura.id
        )
        return

    if fatura.status != novo_status:
        fatura.status = novo_status
        if novo_status == 'pago':
            fatura.data_pagamento = datetime.utcnow()
        db.session.commit()

        LogService.info(
            acao='asaas_webhook_processado',
            mensagem=f'Fatura {fatura.id} atualizada para "{novo_status}" via webhook "{evento}"',
            entidade='Fatura',
            entidade_id=fatura.id
        )


def _mapear_status(evento: str) -> str | None:
    if evento in ('PAYMENT_RECEIVED', 'PAYMENT_CONFIRMED'):
        return 'pago'
    if evento == 'PAYMENT_OVERDUE':
        return 'vencido'
    if evento in ('PAYMENT_DELETED', 'PAYMENT_REFUNDED'):
        return 'cancelado'
    return None


def _obter_ou_criar_customer(client: Client) -> str:
    external_reference = f'client-{client.id}'
    existente = asaas_client.find_customer_by_reference(external_reference)
    if existente:
        return existente['id']

    criado = asaas_client.create_customer(
        name=client.nome,
        cpf_cnpj=client.cpf,
        email=client.email,
        phone=client.telefone,
        external_reference=external_reference
    )
    return criado['id']


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return datetime.strptime(value, '%Y-%m-%d').date()


def _validar_competencia(competencia: str) -> None:
    try:
        datetime.strptime(competencia, '%Y-%m')
    except ValueError:
        raise ValueError('Competência deve estar no formato YYYY-MM (ex.: 2026-08).')
