"""Receipt-only ASAAS platform webhook ledger, separate from tenant payments."""
from datetime import datetime

from extensions import db


class PlatformAsaasWebhookEvent(db.Model):
    __tablename__ = 'platform_asaas_webhook_events'
    __table_args__ = (db.UniqueConstraint('event_id', name='uq_platform_asaas_webhook_event_id'),)

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.String(255), nullable=False)
    event_type = db.Column(db.String(100), nullable=False)
    external_payment_id = db.Column(db.String(100), nullable=False)
    external_reference = db.Column(db.String(255), nullable=True)
    payload_hash = db.Column(db.String(64), nullable=False)
    received_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
