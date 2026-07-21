# backend/models/setting.py
from datetime import datetime

from extensions import db


class Setting(db.Model):
    __tablename__ = 'settings'

    id = db.Column(db.Integer, primary_key=True)
    chave = db.Column(db.String(100), nullable=False, unique=True)
    valor = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'chave': self.chave,
            'valor': self.valor
        }