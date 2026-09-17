"""C5.1/C5.2: energia canônica e tarifa manual; termina no DTO de resultado."""
from decimal import Context, Decimal, ROUND_HALF_UP, localcontext

from services.billing_calculation_contracts import (
    BillingCalculationContext, BillingCalculationEngine as EngineContract,
    BillingCalculationResult, BillingCalculationStrategy, BillingRuleSnapshot,
    CalculationMemory, CalculationMethod, DiscountType, ResolvedBillingRule,
)
from services.invoice_compensation import BillingEnergyInput
from services.invoice_normalization_service import InvoiceNormalized


class BillingCalculationError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def _nonnegative_decimal(value, code):
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise BillingCalculationError(code, 'Exige Decimal finito não negativo.')
    return value


def _validate_context(invoice, rule, context):
    if (not isinstance(invoice, InvoiceNormalized) or not isinstance(rule, ResolvedBillingRule)
            or not isinstance(context, BillingCalculationContext)):
        raise BillingCalculationError('invalid_context', 'Exige DTOs de invoice, regra e contexto.')
    for name in ('empresa_id', 'client_id', 'consumer_unit_id'):
        if getattr(invoice, name) != getattr(context, name):
            raise BillingCalculationError('invalid_context', 'Invoice não corresponde ao contexto resolvido.')
    target = {'company': context.empresa_id, 'client': context.client_id,
              'consumer_unit': context.consumer_unit_id}[rule.source_scope]
    if rule.source_id != target:
        raise BillingCalculationError('invalid_context', 'Fonte da regra não corresponde ao target.')


class _EstrategiaTarifaConfigurada(BillingCalculationStrategy):
    def _percentual_desconto(self, rule):
        if rule.discount_type == DiscountType.NONE:
            if rule.discount_value is not None:
                raise BillingCalculationError('invalid_discount', 'Desconto none exige valor ausente.')
            return Decimal('0')
        if rule.discount_type == DiscountType.PERCENTAGE:
            percentage = _nonnegative_decimal(rule.discount_value, 'invalid_discount')
            if percentage > 100:
                raise BillingCalculationError('invalid_discount', 'Percentual deve estar entre 0 e 100.')
            return percentage
        raise BillingCalculationError('unsupported_discount_type', 'Método suporta none ou percentage.')

    def calculate(self, *, invoice: InvoiceNormalized, rule: ResolvedBillingRule,
                  context: BillingCalculationContext) -> BillingCalculationResult:
        _validate_context(invoice, rule, context)
        if rule.calculation_method != self.method:
            raise BillingCalculationError('unsupported_calculation_method', 'Strategy incompatível com método.')
        energy_input = invoice.billing_energy_input
        if not isinstance(energy_input, BillingEnergyInput):
            raise BillingCalculationError('required_energy_data_missing', 'BillingEnergyInput obrigatório.')
        try:
            energy = energy_input.require_valid()
        except ValueError as exc:
            raise BillingCalculationError('required_energy_data_missing', str(exc)) from exc
        energy = _nonnegative_decimal(energy, 'invalid_energy_input')
        if (energy_input.competencia != context.competencia
                or energy_input.fatura_concessionaria_id != context.fatura_concessionaria_id):
            raise BillingCalculationError('invalid_context', 'Origem energética não corresponde à fatura/competência.')

        tariff = rule.tariff_configuration
        modifiers = rule.billing_modifiers
        if (tariff.tariff_hfp is not None or tariff.tariff_hp is not None
                or modifiers.exclude_pis_cofins is True or modifiers.icms_policy is not None
                or modifiers.exclude_tariff_flag is True or modifiers.grace_period.enabled is True
                or modifiers.recurring_additional_cost is not None):
            raise BillingCalculationError('unsupported_billing_configuration',
                                          'Estratégia não executa modificadores, adicional ou HP/HFP.')
        company_tariff = _nonnegative_decimal(tariff.company_tariff, 'invalid_company_tariff')
        percentage = self._percentual_desconto(rule)

        # Precisão suficiente para produtos/subtrações exatos, independente do contexto global.
        precision = sum(len(v.as_tuple().digits) + abs(v.as_tuple().exponent)
                        for v in (energy, company_tariff, percentage) if v is not None) + 12
        with localcontext(Context(prec=precision, rounding=ROUND_HALF_UP)):
            gross = energy * company_tariff
            if percentage is None:
                discount = Decimal('0')
                effective_tariff = company_tariff
            else:
                fraction = percentage / Decimal('100')
                discount = gross * fraction
                effective_tariff = company_tariff * (Decimal('1') - fraction)
            net = gross - discount
            final = net.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        return BillingCalculationResult(
            context=context, rule_snapshot=BillingRuleSnapshot(rule),
            energy_base_kwh=energy, energia_compensada_kwh=energy,
            tariff_value=company_tariff, gross_base=gross, discount_amount=discount,
            hub_amount=final,
            calculation_memory=CalculationMemory(
                energy_source='invoice.billing_energy_input.energia_compensada_cobravel_kwh',
                energy_reference=f'fatura_concessionaria:{context.fatura_concessionaria_id}:{context.competencia}',
                company_tariff_used=company_tariff, discount_percentage=percentage,
                effective_company_tariff=effective_tariff, net_amount_before_rounding=net,
                monetary_rounding='ROUND_HALF_UP:0.01;final_only',
                desconto_aplicado=(None if self.method == CalculationMethod.ENERGIA_COMPENSADA
                                  else percentage is not None and rule.discount_type == DiscountType.PERCENTAGE),
            ),
        )


class CompensatedEnergyBillingStrategy(_EstrategiaTarifaConfigurada):
    method = CalculationMethod.ENERGIA_COMPENSADA


class EstrategiaTarifaFixa(_EstrategiaTarifaConfigurada):
    method = CalculationMethod.TARIFA_FIXA


class EstrategiaTarifaEspecifica(_EstrategiaTarifaConfigurada):
    method = CalculationMethod.TARIFA_ESPECIFICA

    def _percentual_desconto(self, rule):
        # Configuração compartilhada permanece no snapshot; não participa deste método.
        return None


class BillingCalculationEngine(EngineContract):
    def calculate(self, *, invoice: InvoiceNormalized, rule: ResolvedBillingRule,
                  context: BillingCalculationContext) -> BillingCalculationResult:
        _validate_context(invoice, rule, context)
        strategy = {
            CalculationMethod.ENERGIA_COMPENSADA: CompensatedEnergyBillingStrategy,
            CalculationMethod.TARIFA_FIXA: EstrategiaTarifaFixa,
            CalculationMethod.TARIFA_ESPECIFICA: EstrategiaTarifaEspecifica,
        }.get(rule.calculation_method)
        if strategy is None:
            raise BillingCalculationError('unsupported_calculation_method', 'Método ainda não implementado.')
        return strategy().calculate(invoice=invoice, rule=rule, context=context)
