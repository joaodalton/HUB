from datetime import datetime

from extensions import TenantMixin, db


class Fatura(TenantMixin, db.Model):
    __tablename__ = 'faturas'
    __table_args__ = (
        db.UniqueConstraint('empresa_id', 'asaas_id', name='uq_faturas_empresa_asaas_id'),
        db.CheckConstraint("origem IN ('manual', 'automatica')", name='ck_faturas_origem'),
        db.CheckConstraint(
            "asaas_status IN ('pending', 'received', 'overdue', 'canceled', 'refunded')",
            name='ck_faturas_asaas_status',
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    consumer_unit_id = db.Column(db.Integer, db.ForeignKey('consumer_units.id'), nullable=False)
    concessionaria = db.Column(db.String(50), nullable=False)
    competencia = db.Column(db.String(7), nullable=False)
    valor = db.Column(db.Numeric(10, 2), nullable=False)
    mes_vencimento = db.Column(db.Date, nullable=False)
    origem = db.Column(db.String(20), nullable=False, default='manual')
    asaas_id = db.Column(db.String(100), nullable=False)
    asaas_status = db.Column(db.String(20), nullable=False, default='pending')
    boleto_url = db.Column(db.String(2048), nullable=True)
    linha_digitavel = db.Column(db.String(100), nullable=True)
    codigo_barras = db.Column(db.String(100), nullable=True)
    criado_por_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    enviado_em = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    client = db.relationship('Client')
    consumer_unit = db.relationship('ConsumerUnit')
    criado_por = db.relationship('User')

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'empresaId': self.empresa_id,
            'clienteId': self.client_id,
            'clienteNome': self.client.nome if self.client else None,
            'ucId': self.consumer_unit_id,
            'ucCodigo': self.consumer_unit.codigo if self.consumer_unit else None,
            'concessionaria': self.concessionaria,
            'competencia': self.competencia,
            'valor': float(self.valor),
            'mesVencimento': self.mes_vencimento.isoformat() if self.mes_vencimento else None,
            'origem': self.origem,
            'asaasId': self.asaas_id,
            'asaasStatus': self.asaas_status,
            'boletoUrl': self.boleto_url,
            'linhaDigitavel': self.linha_digitavel,
            'codigoBarras': self.codigo_barras,
            'criadoPorId': self.criado_por_id,
            'enviadoEm': self.enviado_em.isoformat() if self.enviado_em else None,
            'criadaEm': self.created_at.isoformat() if self.created_at else None,
            'atualizadaEm': self.updated_at.isoformat() if self.updated_at else None,
        }
