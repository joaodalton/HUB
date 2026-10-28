# backend/models/report_template.py
from datetime import datetime

from extensions import db, TenantMixin


class ReportTemplate(TenantMixin, db.Model):
    """Template visual proprio de uma empresa pro gerador de relatorio
    (Relatorios > Template). Complementa os templates fixos do sistema
    definidos em services/report_templates.py -- aqueles valem pra todas as
    empresas e nunca sao salvos aqui; isto aqui e so o que CADA empresa
    cadastra pra si mesma."""
    __tablename__ = 'report_templates'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(60), nullable=False)
    accent_hex = db.Column(db.String(6), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            'id': f'custom:{self.id}',
            'label': self.nome,
            'accentHex': self.accent_hex,
            'editable': True,
        }
