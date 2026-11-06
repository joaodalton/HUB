from datetime import datetime

from extensions import TenantMixin, db
from services.billing_calculation_contracts import BillingRuleScope


_SCOPE_VALUES = ', '.join(f"'{scope.value}'" for scope in BillingRuleScope)


class RegraCobrancaAssignment(TenantMixin, db.Model):
    __tablename__ = 'regra_cobranca_assignments'
    __table_args__ = (
        db.CheckConstraint(
            f'scope_type IN ({_SCOPE_VALUES})',
            name='ck_regra_assignment_scope_type',
        ),
        db.CheckConstraint(
            "(scope_type = 'company' AND client_id IS NULL AND consumer_unit_id IS NULL) OR "
            "(scope_type = 'client' AND client_id IS NOT NULL AND consumer_unit_id IS NULL) OR "
            "(scope_type = 'consumer_unit' AND client_id IS NULL AND consumer_unit_id IS NOT NULL)",
            name='ck_regra_assignment_target',
        ),
        db.Index(
            'uq_regra_assignment_company_ativo',
            'empresa_id',
            unique=True,
            postgresql_where=db.text("ativo IS TRUE AND scope_type = 'company'"),
            sqlite_where=db.text("ativo = 1 AND scope_type = 'company'"),
        ),
        db.Index(
            'uq_regra_assignment_client_ativo',
            'empresa_id', 'client_id',
            unique=True,
            postgresql_where=db.text("ativo IS TRUE AND scope_type = 'client'"),
            sqlite_where=db.text("ativo = 1 AND scope_type = 'client'"),
        ),
        db.Index(
            'uq_regra_assignment_uc_ativo',
            'empresa_id', 'consumer_unit_id',
            unique=True,
            postgresql_where=db.text("ativo IS TRUE AND scope_type = 'consumer_unit'"),
            sqlite_where=db.text("ativo = 1 AND scope_type = 'consumer_unit'"),
        ),
        db.Index('ix_regra_assignment_empresa_scope', 'empresa_id', 'scope_type'),
    )

    id = db.Column(db.Integer, primary_key=True)
    grupo_regra_cobranca_id = db.Column(
        db.Integer, db.ForeignKey('grupos_regra_cobranca.id'), nullable=False, index=True,
    )
    scope_type = db.Column(db.String(20), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True, index=True)
    consumer_unit_id = db.Column(
        db.Integer, db.ForeignKey('consumer_units.id'), nullable=True, index=True,
    )
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    grupo_regra_cobranca = db.relationship('GrupoRegraCobranca')
    client = db.relationship('Client')
    consumer_unit = db.relationship('ConsumerUnit')

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'empresaId': self.empresa_id,
            'grupoRegraCobrancaId': self.grupo_regra_cobranca_id,
            'scopeType': self.scope_type,
            'clientId': self.client_id,
            'consumerUnitId': self.consumer_unit_id,
            'ativo': self.ativo,
            'criadoEm': self.created_at.isoformat() if self.created_at else None,
            'atualizadoEm': self.updated_at.isoformat() if self.updated_at else None,
        }
