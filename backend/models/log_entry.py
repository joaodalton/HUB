# backend/models/log_entry.py
from datetime import datetime

from extensions import db, TenantMixin


class LogEntry(TenantMixin, db.Model):
    __tablename__ = 'logs'

    # Sobrescreve a coluna da TenantMixin: aqui empresa_id pode ser nulo
    # porque o log de exclusao de uma empresa e gravado DEPOIS que ela deixa
    # de existir (ver services/empresa_service.py:excluir_empresa).
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresas.id'), nullable=True, index=True)

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
