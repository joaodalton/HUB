from datetime import datetime

from extensions import TenantMixin, db


class WhatsappIntegration(TenantMixin, db.Model):
    """Uma configuracao Meta Cloud API por empresa na primeira versao."""
    __tablename__ = 'whatsapp_integrations'
    __table_args__ = (
        db.UniqueConstraint('empresa_id', name='uq_whatsapp_integrations_empresa'),
        db.UniqueConstraint('phone_number_id', name='uq_whatsapp_integrations_phone_number'),
    )

    id = db.Column(db.Integer, primary_key=True)
    api_credential_id = db.Column(db.Integer, db.ForeignKey('api_credentials.id'), nullable=False, unique=True)
    phone_number_id = db.Column(db.String(100), nullable=False)
    business_account_id = db.Column(db.String(100), nullable=False)
    display_phone_number = db.Column(db.String(40), nullable=True)
    verified_name = db.Column(db.String(150), nullable=True)
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    credential = db.relationship('ApiCredential')

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'phoneNumberId': self.phone_number_id,
            'businessAccountId': self.business_account_id,
            'displayPhoneNumber': self.display_phone_number,
            'verifiedName': self.verified_name,
            'enabled': self.enabled,
            'configured': bool(self.credential and self.credential.segredo_encrypted),
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None,
        }


class WhatsappConversation(TenantMixin, db.Model):
    __tablename__ = 'whatsapp_conversations'
    __table_args__ = (db.UniqueConstraint('empresa_id', 'phone_number', name='uq_whatsapp_conversations_empresa_phone'),)

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    consumer_unit_id = db.Column(db.Integer, db.ForeignKey('consumer_units.id'), nullable=True)
    phone_number = db.Column(db.String(30), nullable=False)
    contact_name = db.Column(db.String(150), nullable=True)
    last_message_at = db.Column(db.DateTime, nullable=True, index=True)
    unread_count = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    client = db.relationship('Client')
    consumer_unit = db.relationship('ConsumerUnit')

    def to_dict(self, *, last_message=None) -> dict:
        return {
            'id': self.id,
            'clientId': self.client_id,
            'clientName': self.client.nome if self.client else None,
            'consumerUnitId': self.consumer_unit_id,
            'consumerUnitCode': self.consumer_unit.codigo if self.consumer_unit else None,
            'phoneNumber': self.phone_number,
            'contactName': self.contact_name,
            'lastMessageAt': self.last_message_at.isoformat() if self.last_message_at else None,
            'unreadCount': self.unread_count,
            'lastMessage': last_message.to_dict() if last_message else None,
        }


class WhatsappMessage(TenantMixin, db.Model):
    __tablename__ = 'whatsapp_messages'
    __table_args__ = (
        db.UniqueConstraint('meta_message_id', name='uq_whatsapp_messages_meta_message'),
        db.CheckConstraint("direction IN ('inbound', 'outbound')", name='ck_whatsapp_messages_direction'),
        db.CheckConstraint("status IN ('queued', 'sent', 'delivered', 'read', 'failed', 'received')", name='ck_whatsapp_messages_status'),
    )

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('whatsapp_conversations.id'), nullable=False, index=True)
    message_template_id = db.Column(db.Integer, db.ForeignKey('message_templates.id'), nullable=True)
    direction = db.Column(db.String(10), nullable=False)
    message_type = db.Column(db.String(20), nullable=False, default='text')
    body = db.Column(db.Text, nullable=False, default='')
    status = db.Column(db.String(20), nullable=False)
    meta_message_id = db.Column(db.String(150), nullable=True)
    provider_error = db.Column(db.String(500), nullable=True)
    sent_at = db.Column(db.DateTime, nullable=True)
    delivered_at = db.Column(db.DateTime, nullable=True)
    read_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    conversation = db.relationship('WhatsappConversation', backref=db.backref('messages', cascade='all, delete-orphan'))
    template = db.relationship('MessageTemplate')

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'conversationId': self.conversation_id,
            'templateId': self.message_template_id,
            'direction': self.direction,
            'type': self.message_type,
            'body': self.body,
            'status': self.status,
            'providerError': self.provider_error,
            'sentAt': self.sent_at.isoformat() if self.sent_at else None,
            'deliveredAt': self.delivered_at.isoformat() if self.delivered_at else None,
            'readAt': self.read_at.isoformat() if self.read_at else None,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
        }
