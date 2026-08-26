# backend/models/fatura.py
from datetime import datetime

from extensions import db, TenantMixin

STATUSES = ('pendente', 'pago', 'vencido', 'cancelado')


class Fatura(TenantMixin, db.Model):
    __tablename__ = 'faturas'

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    consumer_unit_id = db.Column(db.Integer, db.ForeignKey('consumer_units.id'), nullable=True)

    competencia = db.Column(db.String(7), nullable=False)  # 'YYYY-MM'
    valor_original = db.Column(db.Numeric(10, 2), nullable=True)  # valor da fatura da concessionária, se informado
    desconto_percentual = db.Column(db.Numeric(5, 2), nullable=True)
    valor_cobrado = db.Column(db.Numeric(10, 2), nullable=False)  # valor de verdade cobrado do cliente (com desconto)
    vencimento = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pendente')

    # Referências do ASAAS -- nunca preenchidas na mão, sempre pelo
    # fatura_service.py na hora de criar/atualizar a cobrança.
    asaas_customer_id = db.Column(db.String(50), nullable=True)
    asaas_charge_id = db.Column(db.String(50), nullable=True, unique=True, index=True)
    forma_pagamento = db.Column(db.String(20), nullable=True)  # BOLETO, PIX, CREDIT_CARD, UNDEFINED
    link_pagamento = db.Column(db.String(500), nullable=True)
    data_pagamento = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    client = db.relationship('Client')
    consumer_unit = db.relationship('ConsumerUnit')

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'clienteId': self.client_id,
            'clienteNome': self.client.nome if self.client else None,
            'ucId': self.consumer_unit_id,
            'ucCodigo': self.consumer_unit.codigo if self.consumer_unit else None,
            'competencia': self.competencia,
            'valorOriginal': float(self.valor_original) if self.valor_original is not None else None,
            'descontoPercentual': float(self.desconto_percentual) if self.desconto_percentual is not None else None,
            'valorCobrado': float(self.valor_cobrado),
            'vencimento': self.vencimento.isoformat() if self.vencimento else None,
            'status': self.status,
            'formaPagamento': self.forma_pagamento,
            'linkPagamento': self.link_pagamento,
            'dataPagamento': self.data_pagamento.isoformat() if self.data_pagamento else None,
            'criadoEm': self.created_at.isoformat() if self.created_at else None
        }
