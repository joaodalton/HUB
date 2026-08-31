# backend/models/invitation.py
from datetime import datetime

from extensions import db

STATUSES = ('pending', 'accepted', 'expired', 'revoked')


class Invitation(db.Model):
    __tablename__ = 'invitations'

    # SEM TenantMixin -- o fluxo de aceitar convite roda sem sessao
    # autenticada (a pessoa ainda nao tem usuario), entao g.current_empresa_id
    # nao existe nesse ponto. Filtro por empresa e feito explicitamente no
    # service, mesma linha do que ja fizemos com GoogleAccount/User.
    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresas.id'), nullable=False, index=True)
    email = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    token_hash = db.Column(db.String(64), nullable=False, unique=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    invited_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    accepted_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='pending')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'empresaId': self.empresa_id,
            'email': self.email,
            'role': self.role,
            'expiresAt': self.expires_at.isoformat() if self.expires_at else None,
            'invitedBy': self.invited_by,
            'acceptedAt': self.accepted_at.isoformat() if self.accepted_at else None,
            'status': self.status,
            'criadoEm': self.created_at.isoformat() if self.created_at else None
        }