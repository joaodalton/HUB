# backend/models/email_template.py
from datetime import datetime

from extensions import db


class EmailTemplate(db.Model):
    __tablename__ = 'email_templates'

    # SEM TenantMixin -- templates de e-mail sao globais da plataforma hoje
    # (todo tenant recebe o mesmo texto-base do HUB). Se um dia precisar
    # personalizar por empresa, adicionar empresa_id nullable aqui e cair
    # pro template global quando ausente.
    id = db.Column(db.Integer, primary_key=True)
    chave = db.Column(db.String(50), nullable=False, unique=True)
    nome = db.Column(db.String(150), nullable=False)
    assunto = db.Column(db.String(255), nullable=False)
    corpo = db.Column(db.Text, nullable=False)
    variaveis_disponiveis = db.Column(db.String(255), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            'chave': self.chave,
            'nome': self.nome,
            'assunto': self.assunto,
            'corpo': self.corpo,
            'variaveisDisponiveis': self.variaveis_disponiveis.split(',') if self.variaveis_disponiveis else []
        }