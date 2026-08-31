from datetime import datetime

from extensions import TenantMixin, db


class MessageTemplate(TenantMixin, db.Model):
    __tablename__ = 'message_templates'
    __table_args__ = (
        db.UniqueConstraint('empresa_id', 'canal', 'chave', name='uq_message_templates_empresa_canal_chave'),
        db.CheckConstraint("canal IN ('email', 'whatsapp')", name='ck_message_templates_canal'),
    )

    id = db.Column(db.Integer, primary_key=True)
    canal = db.Column(db.String(20), nullable=False)
    chave = db.Column(db.String(50), nullable=False)
    nome = db.Column(db.String(150), nullable=False)
    assunto = db.Column(db.String(255), nullable=False, default='')
    corpo = db.Column(db.Text, nullable=False)
    variaveis_permitidas = db.Column(db.String(255), nullable=False, default='')
    padrao = db.Column(db.Boolean, nullable=False, default=False)
    origem_chave = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        return {'id': self.id, 'canal': self.canal, 'chave': self.chave, 'nome': self.nome,
                'assunto': self.assunto if self.canal == 'email' else None, 'corpo': self.corpo,
                'variaveisPermitidas': _variables(self.variaveis_permitidas), 'padrao': self.padrao,
                'origemChave': self.origem_chave, 'criadoEm': self.created_at.isoformat() if self.created_at else None,
                'atualizadoEm': self.updated_at.isoformat() if self.updated_at else None}


def _variables(value: str) -> list[str]:
    return [item for item in value.split(',') if item]
