"""Unica excecao de lookup cross-tenant: localizar e autenticar o webhook ASAAS."""
from datetime import datetime
import hashlib
import json
import secrets

from flask import g
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from extensions import db
from models.api_credential import ApiCredential
from models.fatura import Fatura
from models.payment_webhook_event import PaymentWebhookEvent
from services.asaas_client import AsaasError, ambiente_asaas
from utils.crypto import decrypt_value


STATUS = {'PENDING': 'pending', 'RECEIVED': 'received', 'CONFIRMED': 'received',
          'RECEIVED_IN_CASH': 'received', 'OVERDUE': 'overdue', 'REFUNDED': 'refunded'}
EVENTS = frozenset({
    'PAYMENT_CREATED', 'PAYMENT_UPDATED', 'PAYMENT_CONFIRMED', 'PAYMENT_RECEIVED',
    'PAYMENT_OVERDUE', 'PAYMENT_DELETED', 'PAYMENT_RESTORED', 'PAYMENT_REFUNDED',
    'PAYMENT_PARTIALLY_REFUNDED', 'PAYMENT_RECEIVED_IN_CASH_UNDONE',
    'PAYMENT_BANK_SLIP_CANCELLED', 'PAYMENT_BANK_SLIP_VIEWED', 'PAYMENT_CHECKOUT_VIEWED',
})


class WebhookError(ValueError):
    def __init__(self, status=401):
        self.status = status
        super().__init__('Webhook nao aceito.')


def _text(value, limit):
    return isinstance(value, str) and 0 < len(value) <= limit and bool(value.strip())


def _resolver_e_autenticar(payment, token):
    # Core + conexao propria: nenhum bypass ORM exportado, nenhum payload financeiro retornado.
    table = Fatura.__table__
    columns = (table.c.id, table.c.empresa_id, table.c.asaas_id, table.c.external_reference)
    reference = payment.get('externalReference')
    with db.engine.connect() as connection:
        rows = connection.execute(select(*columns).where(
            table.c.external_reference == reference).limit(2)).all() if reference else []
        if not rows:
            rows = connection.execute(select(*columns).where(
                table.c.asaas_id == payment['id']).limit(2)).all()
        if len(rows) != 1:
            raise WebhookError()
        row = rows[0]
        if ((row.asaas_id and row.asaas_id != payment['id'])
                or (reference and row.external_reference and reference != row.external_reference)):
            raise WebhookError()
        credentials = ApiCredential.__table__
        try:
            encrypted = connection.execute(select(credentials.c.segredo_encrypted).where(
                credentials.c.empresa_id == row.empresa_id,
                credentials.c.provider == 'asaas', credentials.c.interna.is_(False),
                credentials.c.nome == f'webhook_token_{ambiente_asaas()}',
            )).scalar_one_or_none()
            expected = decrypt_value(encrypted) if encrypted else ''
        except (ValueError, RuntimeError, AsaasError):
            raise WebhookError() from None
        if not expected or not secrets.compare_digest(token.encode('utf-8'), expected.encode('utf-8')):
            raise WebhookError()
        return row.id, row.empresa_id


def processar_webhook(payload, token):
    payment = payload.get('payment') if isinstance(payload, dict) else None
    if (not isinstance(payment, dict) or not _text(payment.get('id'), 100)
            or not _text(payload.get('id'), 255) or not _text(payload.get('event'), 100)
            or (payment.get('externalReference') is not None
                and not _text(payment['externalReference'], 255))):
        raise WebhookError(400)
    if not isinstance(token, str) or len(token) > 10000:
        raise WebhookError()
    previous_tenant = getattr(g, 'current_empresa_id', None)
    try:
        fatura_id, empresa_id = _resolver_e_autenticar(payment, token)
        g.current_empresa_id = empresa_id
        event = PaymentWebhookEvent(
            empresa_id=empresa_id, fatura_id=fatura_id, provider='asaas',
            event_id=payload['id'], event_type=payload['event'],
            external_payment_id=payment['id'], external_reference=payment.get('externalReference'),
            payload_hash=hashlib.sha256(json.dumps(payload, sort_keys=True,
                separators=(',', ':'), ensure_ascii=True).encode()).hexdigest(),
        )
        db.session.add(event)
        try:
            # Unicidade arbitra concorrentes antes de qualquer efeito na Fatura.
            db.session.flush()
        except IntegrityError:
            db.session.rollback()
            existing = PaymentWebhookEvent.query.filter_by(
                empresa_id=empresa_id, provider='asaas', event_id=payload['id'],
                fatura_id=fatura_id, external_payment_id=payment['id'],
                event_type=payload['event'],
            ).first()
            if not existing or not existing.processed_at:
                raise WebhookError(409)
            return
        fatura = Fatura.query.filter_by(id=fatura_id, empresa_id=empresa_id).with_for_update().first()
        if not fatura or (fatura.asaas_id and fatura.asaas_id != payment['id']):
            raise WebhookError(409)
        _aplicar(fatura, payload['event'], payment)
        event.processed_at = datetime.utcnow()
        # Ledger e espelho atomicos. Nenhum LogService (commit proprio) ou efeito externo aqui.
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise WebhookError(503) from None
    except Exception:
        db.session.rollback()
        raise
    finally:
        g.current_empresa_id = previous_tenant


def _aplicar(fatura, event_type, payment):
    if event_type not in EVENTS or not isinstance(payment.get('status'), str):
        raise WebhookError(422)
    status = 'canceled' if event_type == 'PAYMENT_DELETED' else STATUS.get(payment['status'])
    if status is None:
        # Nao converter estados novos/nao suportados em pending e perder informacao financeira.
        raise WebhookError(422)
    fatura.asaas_status = status
    for source, target, limit in (
        ('bankSlipUrl', 'boleto_url', 2048), ('nossoNumero', 'codigo_barras', 100),
        ('identificationField', 'linha_digitavel', 100),
    ):
        if source in payment:
            value = payment[source]
            if value is not None and not _text(value, limit):
                raise WebhookError(400)
            setattr(fatura, target, value)
    if not payment.get('bankSlipUrl') and 'invoiceUrl' in payment:
        value = payment['invoiceUrl']
        if value is not None and not _text(value, 2048):
            raise WebhookError(400)
        fatura.boleto_url = value
    # B1 conserva propriedade da emissao/reconciliacao e do workflow interno.
    # Nao preencher asaas_id nem liberar reservas a partir de um webhook.
