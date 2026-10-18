"""Tentativas de cálculo e resultados financeiros calculados e auditáveis."""
from datetime import datetime

from sqlalchemy import event

from extensions import TenantMixin, db
from services.invoice_normalization_service import json_safe


class BillingCalculationSnapshot(TenantMixin, db.Model):
    __tablename__ = 'billing_calculation_snapshots'
    __table_args__ = (
        db.UniqueConstraint('empresa_id', 'fingerprint', name='uq_billing_snapshot_empresa_fingerprint'),
        db.UniqueConstraint('id', 'empresa_id', name='uq_billing_snapshot_id_empresa'),
        db.UniqueConstraint('id', 'empresa_id', 'fatura_concessionaria_id',
                            name='uq_billing_snapshot_id_empresa_invoice'),
        db.ForeignKeyConstraint(
            ['fatura_concessionaria_id', 'empresa_id'],
            ['faturas_concessionarias.id', 'faturas_concessionarias.empresa_id'],
            name='fk_billing_snapshot_invoice_tenant',
        ),
        db.CheckConstraint('length(fingerprint) = 64', name='ck_billing_snapshot_fingerprint'),
    )

    id = db.Column(db.Integer, primary_key=True)
    fatura_concessionaria_id = db.Column(
        db.Integer, nullable=False, index=True,
    )
    fingerprint = db.Column(db.String(64), nullable=False)
    regra_snapshot = db.Column(db.JSON, nullable=False)
    entrada_normalizada = db.Column(db.JSON, nullable=False)
    resultado = db.Column(db.JSON, nullable=False)
    valor_final = db.Column(db.Numeric(18, 2), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    fatura_concessionaria = db.relationship('FaturaConcessionaria', viewonly=True)

    def __init__(self, **kwargs):
        for field in ('regra_snapshot', 'entrada_normalizada', 'resultado'):
            if field in kwargs:
                kwargs[field] = json_safe(kwargs[field])
        super().__init__(**kwargs)


class BillingCalculationExecution(TenantMixin, db.Model):
    __tablename__ = 'billing_calculation_executions'
    __table_args__ = (
        db.CheckConstraint(
            "status IN ('CALCULATED', 'REVIEW_REQUIRED', 'MISSING_DATA', 'UNSUPPORTED', 'ERROR')",
            name='ck_billing_execution_status',
        ),
        db.CheckConstraint(
            "(status = 'CALCULATED' AND snapshot_id IS NOT NULL) OR "
            "(status <> 'CALCULATED' AND snapshot_id IS NULL)",
            name='ck_billing_execution_snapshot',
        ),
        db.ForeignKeyConstraint(
            ['fatura_concessionaria_id', 'empresa_id'],
            ['faturas_concessionarias.id', 'faturas_concessionarias.empresa_id'],
            name='fk_billing_execution_invoice_tenant',
        ),
        db.ForeignKeyConstraint(
            ['snapshot_id', 'empresa_id', 'fatura_concessionaria_id'],
            ['billing_calculation_snapshots.id', 'billing_calculation_snapshots.empresa_id',
             'billing_calculation_snapshots.fatura_concessionaria_id'],
            name='fk_billing_execution_snapshot_invoice_tenant',
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    fatura_concessionaria_id = db.Column(
        db.Integer, nullable=False, index=True,
    )
    snapshot_id = db.Column(
        db.Integer, nullable=True, index=True,
    )
    status = db.Column(db.String(20), nullable=False)
    auditoria = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    fatura_concessionaria = db.relationship('FaturaConcessionaria', viewonly=True)
    snapshot = db.relationship('BillingCalculationSnapshot', viewonly=True)

    def __init__(self, **kwargs):
        if 'auditoria' in kwargs:
            kwargs['auditoria'] = json_safe(kwargs['auditoria'])
        super().__init__(**kwargs)


def _impedir_alteracao(mapper, connection, target):
    raise ValueError('Registro de cálculo é imutável.')


for _model in (BillingCalculationSnapshot, BillingCalculationExecution):
    event.listen(_model, 'before_update', _impedir_alteracao)
    event.listen(_model, 'before_delete', _impedir_alteracao)
