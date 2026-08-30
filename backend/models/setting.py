# backend/models/setting.py
from datetime import datetime

from extensions import db, TenantMixin


class Setting(TenantMixin, db.Model):
    __tablename__ = 'settings'

    id = db.Column(db.Integer, primary_key=True)
    chave = db.Column(db.String(100), nullable=False)
    valor = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('empresa_id', 'chave', name='uq_settings_empresa_chave'),
    )

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'chave': self.chave,
            'valor': self.valor
        }
