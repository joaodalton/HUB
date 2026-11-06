"""Receive platform events without applying SaaS billing rules not yet defined."""
import hashlib
import json
import secrets

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from config import Config
from extensions import db
from models.platform_asaas_webhook_event import PlatformAsaasWebhookEvent
from services.asaas_webhook_service import WebhookError, _text


def receive_platform_webhook(payload, token):
    expected = Config.PLATFORM_ASAAS_WEBHOOK_TOKEN
    if (not expected or not isinstance(token, str) or len(token) > 10000
            or not secrets.compare_digest(token.encode('utf-8'), expected.encode('utf-8'))):
        raise WebhookError()
    payment = payload.get('payment') if isinstance(payload, dict) else None
    if (not isinstance(payment, dict) or not _text(payload.get('id'), 255)
            or not _text(payload.get('event'), 100) or not _text(payment.get('id'), 100)
            or (payment.get('externalReference') is not None
                and not _text(payment['externalReference'], 255))):
        raise WebhookError(400)
    reference = payment.get('externalReference')
    if reference is not None and not reference.startswith('hub-platform-'):
        raise WebhookError(422)
    payload_hash = hashlib.sha256(json.dumps(payload, sort_keys=True,
        separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()
    event = PlatformAsaasWebhookEvent(event_id=payload['id'], event_type=payload['event'],
        external_payment_id=payment['id'], external_reference=payment.get('externalReference'),
        payload_hash=payload_hash)
    db.session.add(event)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        existing = PlatformAsaasWebhookEvent.query.filter_by(event_id=payload['id']).first()
        if existing and existing.payload_hash == payload_hash:
            return
        raise WebhookError(409) from None
    except SQLAlchemyError:
        db.session.rollback()
        raise WebhookError(503) from None
