from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import validates

from extensions import TenantMixin, db
from services.billing_calculation_contracts import (
    BillingMode,
    CalculationMethod,
    DiscountType,
    DueDateBasis,
    TariffBasis,
    TariffSource,
    TariffConfiguration, BillingModifiers, GracePeriod,
)


def _enum_check(column: str, enum_type) -> str:
    values = ', '.join(f"'{item.value}'" for item in enum_type)
    return f'{column} IN ({values})'


class GrupoRegraCobranca(TenantMixin, db.Model):
    __tablename__ = 'grupos_regra_cobranca'
    __table_args__ = (
        db.CheckConstraint(_enum_check('calculation_method', CalculationMethod), name='ck_grupo_regra_calculation_method'),
        db.CheckConstraint(_enum_check('tariff_source', TariffSource), name='ck_grupo_regra_tariff_source'),
        db.CheckConstraint(_enum_check('discount_type', DiscountType), name='ck_grupo_regra_discount_type'),
        db.CheckConstraint(_enum_check('tariff_basis', TariffBasis), name='ck_grupo_regra_tariff_basis'),
        db.CheckConstraint(_enum_check('billing_mode', BillingMode), name='ck_grupo_regra_billing_mode'),
        db.CheckConstraint(_enum_check('due_date_basis', DueDateBasis), name='ck_grupo_regra_due_date_basis'),
        db.CheckConstraint(
            "tariff_source <> 'manual' OR manual_tariff IS NOT NULL",
            name='ck_grupo_regra_manual_tariff',
        ),
        db.CheckConstraint(
            "(discount_type = 'none' AND discount_value IS NULL) OR "
            "(discount_type <> 'none' AND discount_value IS NOT NULL)",
            name='ck_grupo_regra_discount_value',
        ),
        db.CheckConstraint(
            "(tariff_basis = 'documented_component' AND energy_component_index IS NOT NULL "
            "AND energy_component_index >= 0) OR "
            "(tariff_basis <> 'documented_component' AND energy_component_index IS NULL)",
            name='ck_grupo_regra_energy_component',
        ),
        db.CheckConstraint('revision >= 1', name='ck_grupo_regra_revision'),
        db.CheckConstraint(
            'grace_duration_months IS NULL OR (grace_duration_months > 0 AND grace_enabled IS TRUE)',
            name='ck_grupo_regra_grace_duration',
        ),
        db.CheckConstraint("icms_policy IS NULL OR icms_policy = 'exclude'", name='ck_grupo_regra_icms'),
        db.CheckConstraint(
            "(grace_start IS NULL AND grace_end IS NULL) OR "
            "(grace_start IS NOT NULL AND grace_end IS NOT NULL AND grace_start <= grace_end)",
            name='ck_grupo_regra_grace_dates',
        ),
        db.CheckConstraint(
            "grace_enabled IS TRUE OR (grace_without_discount IS NULL AND grace_start IS NULL AND grace_end IS NULL)",
            name='ck_grupo_regra_grace_enabled',
        ),
        db.CheckConstraint(
            "calculation_method NOT IN ('tarifa_especifica', 'tarifa_fixa_com_desconto') OR manual_tariff IS NOT NULL",
            name='ck_grupo_regra_company_tariff',
        ),
        db.CheckConstraint(
            "calculation_method <> 'tarifa_fixa_com_desconto' OR (discount_type = 'percentage' AND discount_value IS NOT NULL)",
            name='ck_grupo_regra_fixed_discount',
        ),
        db.Index(
            'uq_grupos_regra_cobranca_default_ativo',
            'empresa_id',
            unique=True,
            postgresql_where=db.text('ativo IS TRUE AND padrao IS TRUE'),
            sqlite_where=db.text('ativo = 1 AND padrao = 1'),
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    padrao = db.Column(db.Boolean, nullable=False, default=False)

    calculation_method = db.Column(db.String(40), nullable=False)
    tariff_source = db.Column(db.String(20), nullable=False)
    manual_tariff = db.Column(db.Numeric(18, 6), nullable=True)
    tariff_hfp = db.Column(db.Numeric(18, 6), nullable=True)
    tariff_hp = db.Column(db.Numeric(18, 6), nullable=True)
    exclude_pis_cofins = db.Column(db.Boolean, nullable=True)
    icms_policy = db.Column(db.String(20), nullable=True)
    exclude_tariff_flag = db.Column(db.Boolean, nullable=True)
    grace_enabled = db.Column(db.Boolean, nullable=True)
    grace_without_discount = db.Column(db.Boolean, nullable=True)
    grace_duration_months = db.Column(db.Integer, nullable=True)
    # Legado C4.1 preservado apenas para revisão; não pertence à política ativa.
    grace_start = db.Column(db.Date, nullable=True)
    grace_end = db.Column(db.Date, nullable=True)
    recurring_additional_cost = db.Column(db.Numeric(18, 6), nullable=True)
    discount_type = db.Column(db.String(20), nullable=False)
    discount_value = db.Column(db.Numeric(18, 6), nullable=True)
    tariff_basis = db.Column(db.String(40), nullable=False)
    energy_component_index = db.Column(db.Integer, nullable=True)

    billing_mode = db.Column(db.String(20), nullable=False)
    due_date_basis = db.Column(db.String(40), nullable=False)
    due_date_offset_days = db.Column(db.Integer, nullable=False)
    monthly_interest = db.Column(db.Numeric(18, 6), nullable=True)
    fine_percentage = db.Column(db.Numeric(18, 6), nullable=True)

    revision = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    @validates('manual_tariff', 'discount_value', 'monthly_interest', 'fine_percentage',
               'tariff_hfp', 'tariff_hp', 'recurring_additional_cost')
    def _validate_decimal(self, _key, value):
        if value is not None and (not isinstance(value, Decimal) or not value.is_finite()):
            raise ValueError('Valores financeiros devem ser Decimal finito ou null.')
        return value

    @property
    def tariff_configuration(self):
        return TariffConfiguration(self.manual_tariff, self.tariff_hfp, self.tariff_hp)

    @property
    def billing_modifiers(self):
        return BillingModifiers(
            self.exclude_pis_cofins, self.icms_policy, self.exclude_tariff_flag,
            GracePeriod(self.grace_enabled, self.grace_without_discount, self.grace_duration_months),
            self.recurring_additional_cost,
        )

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'empresaId': self.empresa_id,
            'nome': self.nome,
            'descricao': self.descricao,
            'ativo': self.ativo,
            'padrao': self.padrao,
            'calculationMethod': self.calculation_method,
            'tariffSource': self.tariff_source,
            'manualTariff': _decimal_text(self.manual_tariff),
            'tariffConfiguration': {
                'companyTariff': _decimal_text(self.manual_tariff),
                'tariffHfp': _decimal_text(self.tariff_hfp),
                'tariffHp': _decimal_text(self.tariff_hp),
            },
            'billingModifiers': {
                'excludePisCofins': self.exclude_pis_cofins,
                'icmsPolicy': self.icms_policy,
                'excludeTariffFlag': self.exclude_tariff_flag,
                'recurringAdditionalCost': _decimal_text(self.recurring_additional_cost),
                'gracePeriod': {
                    'enabled': self.grace_enabled,
                    'withoutDiscount': self.grace_without_discount,
                    'durationMonths': self.grace_duration_months,
                    'start': self.grace_start.isoformat() if self.grace_start else None,
                    'end': self.grace_end.isoformat() if self.grace_end else None,
                },
            },
            'discountType': self.discount_type,
            'discountValue': _decimal_text(self.discount_value),
            'tariffBasis': self.tariff_basis,
            'energyComponentIndex': self.energy_component_index,
            'billingMode': self.billing_mode,
            'dueDateBasis': self.due_date_basis,
            'dueDateOffsetDays': self.due_date_offset_days,
            'monthlyInterest': _decimal_text(self.monthly_interest),
            'finePercentage': _decimal_text(self.fine_percentage),
            'revision': self.revision,
            'criadoEm': self.created_at.isoformat() if self.created_at else None,
            'atualizadoEm': self.updated_at.isoformat() if self.updated_at else None,
        }


def _decimal_text(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None
