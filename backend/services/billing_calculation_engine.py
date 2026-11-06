"""C5.1/C5.2: energia canônica e tarifa manual; termina no DTO de resultado."""
from dataclasses import replace
from decimal import Context, Decimal, ROUND_HALF_UP, localcontext

from services.billing_calculation_contracts import (
    BillingCalculationContext, BillingCalculationEngine as EngineContract,
    BillingCalculationResult, BillingCalculationStrategy, BillingRuleSnapshot,
    CalculationMemory, CalculationMethod, DiscountType, ResolvedBillingRule,
    BillingCalculationIssue, BillingIssueSeverity, ComponentTreatment,
)
from services.invoice_compensation import BillingEnergyInput, EnergyStatus
from services.commercial_tariff_selector import CommercialTariffSelector, SelectedCommercialTariff
from services.document_tariff_resolver import DocumentTariffResolver
from services.commercial_deduction_resolver import CommercialDeductionResolver, document_tax_audit
from services.fio_b_resolver import FioBResolver
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
                or modifiers.icms_policy is not None
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
                  context: BillingCalculationContext, selected_tariffs=None,
                  deduction_evidence=(), fio_b_tariffs=()) -> BillingCalculationResult:
        _validate_context(invoice, rule, context)
        strategy = {
            CalculationMethod.ENERGIA_COMPENSADA: CompensatedEnergyBillingStrategy,
            CalculationMethod.TARIFA_FIXA: EstrategiaTarifaFixa,
            CalculationMethod.TARIFA_ESPECIFICA: EstrategiaTarifaEspecifica,
        }.get(rule.calculation_method)
        if strategy is None:
            raise BillingCalculationError('unsupported_calculation_method', 'Método ainda não implementado.')
        energy_input = invoice.billing_energy_input
        if (rule.billing_modifiers.exclude_gdii_fio_b is True and isinstance(energy_input, BillingEnergyInput)
                and energy_input.status != EnergyStatus.VALID):
            if (energy_input.competencia != context.competencia
                    or energy_input.fatura_concessionaria_id != context.fatura_concessionaria_id):
                raise BillingCalculationError('invalid_context', 'Origem energética divergente.')
            resolved = CommercialDeductionResolver().resolve(invoice=invoice, rule=rule,
                evidence=deduction_evidence, regulatory_tariffs=fio_b_tariffs)
            return BillingCalculationResult(context=context, rule_snapshot=BillingRuleSnapshot(rule),
                resolution_status=energy_input.status, issues=resolved.issues,
                calculation_memory=CalculationMemory(document_taxes=document_tax_audit(invoice),
                    fio_b_components=tuple(row.to_dict() for row in resolved.fio_b_components),
                    fio_b_treatment=ComponentTreatment.BLOCKED,
                    exclude_gdii_fio_b=rule.billing_modifiers.exclude_gdii_fio_b))
        if selected_tariffs is None:
            base = strategy().calculate(invoice=invoice, rule=rule, context=context)
        else:
            base = self._selected_base(invoice, rule, context, strategy(), selected_tariffs)
        if base.resolution_status != EnergyStatus.VALID:
            return replace(base, calculation_memory=replace(base.calculation_memory,
                document_taxes=document_tax_audit(invoice), fio_b_components=tuple(
                    row.to_dict() for row in FioBResolver().resolve(invoice, regulatory_tariffs=fio_b_tariffs))))
        return self._deduct(base, invoice, rule, deduction_evidence, fio_b_tariffs)

    @staticmethod
    def _selected_base(invoice, rule, context, strategy, selections):
        selections = tuple(selections)
        if any(not isinstance(s, SelectedCommercialTariff) for s in selections):
            raise BillingCalculationError('invalid_tariff_selection', 'Selecao tarifaria tipada obrigatoria.')
        energy_input = invoice.billing_energy_input
        if not isinstance(energy_input, BillingEnergyInput):
            raise BillingCalculationError('required_energy_data_missing', 'BillingEnergyInput obrigatorio.')
        try:
            energy = _nonnegative_decimal(energy_input.require_valid(), 'invalid_energy_input')
        except ValueError as exc:
            raise BillingCalculationError('required_energy_data_missing', str(exc)) from exc
        if (energy_input.competencia != context.competencia
                or energy_input.fatura_concessionaria_id != context.fatura_concessionaria_id):
            raise BillingCalculationError('invalid_context', 'Origem energetica divergente.')
        modifiers, tariff = rule.billing_modifiers, rule.tariff_configuration
        if (tariff.tariff_hfp is not None or tariff.tariff_hp is not None
                or modifiers.grace_period.enabled is True
                or modifiers.recurring_additional_cost is not None):
            raise BillingCalculationError('unsupported_billing_configuration', 'Configuracao fora do escopo.')
        snapshot = BillingRuleSnapshot(rule)
        if any(s.rule_snapshot.to_dict() != snapshot.to_dict() for s in selections):
            raise BillingCalculationError('invalid_tariff_selection', 'Snapshot tarifario divergente.')
        # Reutiliza os resolvedores canonicos para validar origem, cobertura e preco.
        expected = CommercialTariffSelector().select(DocumentTariffResolver().resolve(invoice), rule)
        remaining = list(expected)
        for selection in selections:
            if selection not in remaining:
                raise BillingCalculationError('invalid_tariff_selection', 'Evento ou tarifa nao corresponde a fatura.')
            remaining.remove(selection)
        if remaining or not selections:
            raise BillingCalculationError('invalid_tariff_selection', 'Cobertura tarifaria incompleta.')
        audit = tuple({'selection': s.to_dict(), 'quantity_kwh': s.event.identity.quantidade_kwh}
                      for s in selections)
        invalid = [s for s in selections if s.status != EnergyStatus.VALID]
        if invalid:
            return BillingCalculationResult(
                context=context, rule_snapshot=snapshot, resolution_status=invalid[0].status,
                issues=tuple(issue for s in invalid for issue in s.issues),
                calculation_memory=CalculationMemory(event_calculations=audit),
            )
        percentage = strategy._percentual_desconto(rule)
        numbers = [energy, percentage or Decimal(0)] + [
            value for s in selections for value in (s.event.identity.quantidade_kwh, s.selected_tariff)]
        precision = sum(len(v.as_tuple().digits) + abs(v.as_tuple().exponent) for v in numbers) + 12
        with localcontext(Context(prec=precision, rounding=ROUND_HALF_UP)):
            event_rows = tuple({**row, 'gross_amount': s.event.identity.quantidade_kwh * s.selected_tariff}
                               for row, s in zip(audit, selections))
            gross = sum((row['gross_amount'] for row in event_rows), Decimal(0))
            discount = gross * (percentage or Decimal(0)) / Decimal(100)
            net = gross - discount
        prices = {s.selected_tariff for s in selections}
        return BillingCalculationResult(
            context=context, rule_snapshot=snapshot, energy_base_kwh=energy,
            energia_compensada_kwh=energy, tariff_value=next(iter(prices)) if len(prices) == 1 else None,
            gross_base=gross, discount_amount=discount,
            calculation_memory=CalculationMemory(
                energy_source='invoice.billing_energy_input.energia_compensada_cobravel_kwh',
                energy_reference=f'fatura_concessionaria:{context.fatura_concessionaria_id}:{context.competencia}',
                discount_percentage=percentage, net_amount_before_rounding=net,
                monetary_rounding='ROUND_HALF_UP:0.01;final_only', event_calculations=event_rows,
                desconto_aplicado=percentage is not None and rule.discount_type == DiscountType.PERCENTAGE,
            ),
        )

    @staticmethod
    def _deduct(base, invoice, rule, evidence, fio_b_tariffs):
        resolved = CommercialDeductionResolver().resolve(invoice=invoice, rule=rule, evidence=evidence,
                                                        regulatory_tariffs=fio_b_tariffs)
        modifiers = rule.billing_modifiers
        net = base.calculation_memory.net_amount_before_rounding
        memory = replace(
            base.calculation_memory, deduction_resolution=resolved.to_dict(), post_discount_amount=net,
            pis_amount=resolved.total_pis, cofins_amount=resolved.total_cofins,
            pis_cofins_amount=resolved.total_pis_cofins, fio_b_amount=resolved.total_fio_b,
            exclude_gdii_fio_b=modifiers.exclude_gdii_fio_b,
            document_taxes=document_tax_audit(invoice),
            fio_b_components=tuple(row.to_dict() for row in resolved.fio_b_components),
            pis_cofins_treatment=(ComponentTreatment.NOT_APPLICABLE if modifiers.exclude_pis_cofins is not True
                                  else ComponentTreatment.APPLIED if resolved.total_pis_cofins is not None
                                  else ComponentTreatment.BLOCKED),
            fio_b_treatment=(ComponentTreatment.NOT_APPLICABLE if modifiers.exclude_gdii_fio_b is not True
                            or all(row.status == 'NOT_APPLICABLE' for row in resolved.fio_b_components)
                            else ComponentTreatment.APPLIED if resolved.total_fio_b is not None
                            else ComponentTreatment.BLOCKED),
        )
        issues = base.issues + resolved.issues
        if resolved.status != EnergyStatus.VALID:
            return replace(base, hub_amount=None, resolution_status=resolved.status, issues=issues,
                           calculation_memory=replace(memory, net_amount_before_rounding=None,
                               pis_cofins_treatment=(ComponentTreatment.BLOCKED
                                   if modifiers.exclude_pis_cofins is True else ComponentTreatment.NOT_APPLICABLE),
                               fio_b_treatment=(ComponentTreatment.BLOCKED
                                   if modifiers.exclude_gdii_fio_b is True else ComponentTreatment.NOT_APPLICABLE)))
        numbers = (net, resolved.total_pis_cofins, resolved.total_fio_b)
        precision = sum(len(v.as_tuple().digits) + abs(v.as_tuple().exponent) for v in numbers) + 12
        with localcontext(Context(prec=precision, rounding=ROUND_HALF_UP)):
            post_pis = net - resolved.total_pis_cofins
            raw = post_pis - resolved.total_fio_b
            if raw < 0:
                issues += (BillingCalculationIssue('DEDUCOES_SUPERAM_VALOR_COBRAVEL',
                    BillingIssueSeverity.WARNING, 'Deducoes excedem a cobranca; valor limitado a zero.'),)
            final = max(raw, Decimal(0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return replace(base, hub_amount=final, issues=issues, calculation_memory=replace(
            memory, post_pis_cofins_amount=post_pis, net_amount_before_rounding=raw))
