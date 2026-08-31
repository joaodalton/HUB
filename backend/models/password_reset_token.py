# backend/models/password_reset_token.py
from datetime import datetime

from extensions import db


class PasswordResetToken(db.Model):
    __tablename__ = 'password_reset_tokens'

    # SEM TenantMixin -- mesmo motivo do Invitation (models/invitation.py):
    # o fluxo de "esqueci minha senha" roda sem sessao autenticada, entao
    # g.current_empresa_id nao existe nesse momento. O vinculo com a
    # empresa vem indiretamente via User.
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    token_hash = db.Column(db.String(64), nullable=False, unique=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, nullable=False, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User')