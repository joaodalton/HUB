from datetime import datetime

from extensions import TenantMixin, db


class CrmLead(TenantMixin, db.Model):
    """Leitura local de negocios importados de um CRM externo (ex.: PipeRun).

    Nao cria/atualiza Client automaticamente -- escopo deliberado da v1."""
    __tablename__ = 'crm_leads'
    __table_args__ = (
        db.UniqueConstraint('empresa_id', 'provider', 'external_id', name='uq_crm_leads_empresa_provider_external_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(40), nullable=False)
    external_id = db.Column(db.String(60), nullable=False)
    titulo = db.Column(db.String(255), nullable=True)
    status = db.Column(db.Integer, nullable=True)
    valor = db.Column(db.Numeric(14, 2), nullable=True)
    pipeline_nome = db.Column(db.String(150), nullable=True)
    etapa_nome = db.Column(db.String(150), nullable=True)
    dados_brutos = db.Column(db.JSON, nullable=True)
    criado_em_origem = db.Column(db.DateTime, nullable=True)
    atualizado_em_origem = db.Column(db.DateTime, nullable=True)
    importado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'provider': self.provider,
            'externalId': self.external_id,
            'titulo': self.titulo,
            'status': self.status,
            'valor': str(self.valor) if self.valor is not None else None,
            'pipelineNome': self.pipeline_nome,
            'etapaNome': self.etapa_nome,
            'criadoEmOrigem': self.criado_em_origem.isoformat() if self.criado_em_origem else None,
            'atualizadoEmOrigem': self.atualizado_em_origem.isoformat() if self.atualizado_em_origem else None,
            'importadoEm': self.importado_em.isoformat() if self.importado_em else None,
            'atualizadoEm': self.atualizado_em.isoformat() if self.atualizado_em else None,
        }
