from datetime import datetime

from extensions import db


class Assinatura(db.Model):
    """Plano e ciclo de vida da cobranca da plataforma por empresa."""
    __tablename__ = 'assinaturas'

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresas.id'), nullable=False, unique=True, index=True)
    plano_chave = db.Column(db.String(50), nullable=False, default='starter')
    tipo = db.Column(db.String(20), nullable=False, default='trial')
    status = db.Column(db.String(20), nullable=False, default='trial')
    trial_expira_em = db.Column(db.DateTime, nullable=True)
    inicio_periodo_atual = db.Column(db.DateTime, nullable=True)
    fim_periodo_atual = db.Column(db.DateTime, nullable=True)
    proxima_cobranca = db.Column(db.DateTime, nullable=True)
    asaas_subscription_id = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        from planos.catalogo import get_plano

        plano = get_plano(self.plano_chave)
        return {
            'id': self.id,
            'empresaId': self.empresa_id,
            'planoChave': self.plano_chave,
            'planoNome': plano['nome'],
            'tipo': self.tipo,
            'status': self.status,
            'trialExpiraEm': self.trial_expira_em.isoformat() if self.trial_expira_em else None,
            'proximaCobranca': self.proxima_cobranca.isoformat() if self.proxima_cobranca else None,
        }
