# backend/models/log_entry.py
from datetime import datetime

from extensions import db


class LogEntry(db.Model):
    __tablename__ = 'logs'

    id = db.Column(db.Integer, primary_key=True)
    nivel = db.Column(db.String(20), nullable=False, default='info')
    acao = db.Column(db.String(100), nullable=False)
    entidade = db.Column(db.String(100), nullable=True)
    entidade_id = db.Column(db.Integer, nullable=True)
    mensagem = db.Column(db.Text, nullable=True)
    metadados = db.Column(db.JSON, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'nivel': self.nivel,
            'acao': self.acao,
            'entidade': self.entidade,
            'entidadeId': self.entidade_id,
            'mensagem': self.mensagem,
            'metadados': self.metadados,
            'criadoEm': self.created_at.isoformat() if self.created_at else None
        }