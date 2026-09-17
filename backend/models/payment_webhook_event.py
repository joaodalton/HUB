from datetime import datetime

from extensions import TenantMixin, db


class PaymentWebhookEvent(TenantMixin, db.Model):
    __tablename__ = 'payment_webhook_events'
    __table_args__ = (
        db.UniqueConstraint('provider', 'event_id', name='uq_payment_webhook_provider_event'),
    )

    id = db.Column(db.Integer, primary_key=True)
    fatura_id = db.Column(db.Integer, db.ForeignKey('faturas.id'), nullable=False, index=True)
    provider = db.Column(db.String(40), nullable=False)
    event_id = db.Column(db.String(255), nullable=False)
    event_type = db.Column(db.String(100), nullable=False)
    external_payment_id = db.Column(db.String(100), nullable=False)
    external_reference = db.Column(db.String(255), nullable=True)
    payload_hash = db.Column(db.String(64), nullable=False)
    processed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
