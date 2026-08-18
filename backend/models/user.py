# backend/models/user.py
from datetime import datetime

from extensions import db

ROLES = ('owner', 'admin', 'operator', 'financial', 'viewer')


class User(db.Model):
    __tablename__ = 'users'

    # SEM TenantMixin de proposito -- login localiza o User pelo email
    # (unico em toda a base) antes de existir uma "empresa atual" na
    # sessao. Ver comentario em extensions.py.
    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresas.id'), nullable=False, index=True)
    nome = db.Column(db.String(150), nullable=False, default='')
    email = db.Column(db.String(150), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='viewer')
    status = db.Column(db.String(20), nullable=False, default='ativo')
    email_verified = db.Column(db.Boolean, nullable=False, default=False)
    must_change_password = db.Column(db.Boolean, nullable=False, default=False)
    # Flag global, separado dos papeis que valem apenas dentro da empresa.
    # E concedido exclusivamente pelo script administrativo.
    is_platform_admin = db.Column(db.Boolean, nullable=False, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        # Nunca inclui password_hash na resposta.
        return {
            'id': self.id,
            'empresaId': self.empresa_id,
            'nome': self.nome,
            'email': self.email,
            'role': self.role,
            'status': self.status,
            'emailVerified': self.email_verified,
            'mustChangePassword': self.must_change_password,
            'isPlatformAdmin': self.is_platform_admin
        }
