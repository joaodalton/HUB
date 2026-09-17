import ast
from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime
from decimal import Decimal
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.billing_calculation_contracts import (
    CALCULATION_ENGINE_VERSION, BillingCalculationContext, BillingCalculationEngine,
    BillingCalculationIssue, BillingCalculationResult, BillingCalculationStrategy,
    BillingIssueSeverity, BillingMode, BillingRuleScope, BillingRuleSnapshot,
    CalculationMethod, DiscountType, DueDateBasis, ResolvedBillingRule, TariffBasis, TariffSource,
    CalculationMemory, CalculationBlockCode, ComponentTreatment, required_document_value,
    GracePeriod, BillingModifiers, TariffConfiguration,
)
from services.invoice_normalization_service import json_safe
from services.invoice_parsers.schemas import ExtractionIssue


def rule(**changes):
    values = dict(rule_id=1, rule_name='Regra teste', rule_version='1', source_scope='company',
                  source_id=10, calculation_method='energia_compensada', tariff_source='invoice',
                  discount_type='none', tariff_basis='consumed', billing_mode='auto',
                  due_date_basis='invoice_due_date', due_date_offset_days=0)
    return ResolvedBillingRule(**{**values, **changes})


class BillingContractsTest(unittest.TestCase):
    def test_c42_required_document_data_is_blocking_and_never_defaulted(self):
        for code in (CalculationBlockCode.REQUIRED_TAX_DATA_MISSING,
                     CalculationBlockCode.BASE_TARIFF_WITHOUT_FLAG_MISSING,
                     CalculationBlockCode.REQUIRED_ICMS_DATA_MISSING,
                     CalculationBlockCode.REQUIRED_ENERGY_DATA_MISSING):
            for value, source in ((None, 'invoice.field'), (Decimal('1'), None)):
                issue = required_document_value(value, source=source, missing_code=code)
                self.assertEqual(issue.code, code.value)
                self.assertEqual(issue.severity, 'critical')
                result = self.result(issues=(issue,))
                self.assertIsNone(result.hub_amount)
                self.assertIsNone(result.energy_base_kwh)
            self.assertIsNone(required_document_value(Decimal('0'), source='invoice.field', missing_code=code))
            with self.assertRaises(ValueError):
                required_document_value(1.2, source='invoice.field', missing_code=code)

    def test_c42_audit_contract_keeps_components_distinct_without_calculation(self):
        memory = CalculationMemory(energy_source='document', energy_reference='energy_components[0]',
            company_tariff_used=Decimal('0.734821'), concessionaria_reference_tariff=None,
            pis_cofins_treatment='blocked', icms_treatment='excluded', icms_amount=Decimal('2.123456'),
            tariff_flag_treatment='not_applicable', original_discount_amount=Decimal('10'),
            grace_state='blocked', recurring_additional_cost=Decimal('12.345678'))
        result = self.result(calculation_memory=memory)
        payload = result.to_dict()
        self.assertIsNone(payload['hub_amount'])
        self.assertIsNone(payload['discount_amount'])
        self.assertIsNone(payload['additions_amount'])
        self.assertEqual(payload['calculation_memory']['company_tariff_used'], '0.734821')
        self.assertIsNone(payload['calculation_memory']['concessionaria_reference_tariff'])
        self.assertIsNone(payload['calculation_memory']['pis_cofins_amount'])
        self.assertEqual(payload['calculation_memory']['recurring_additional_cost'], '12.345678')
        self.assertEqual(payload['calculation_memory']['icms_treatment'], 'excluded')
        self.assertEqual(payload['rule_snapshot']['calculation_method'], 'energia_compensada')
        for name in ('company_tariff_used', 'recurring_additional_cost', 'icms_amount'):
            with self.assertRaises(ValueError):
                CalculationMemory(**{name: 1.2})

    def test_c42_snapshot_policy_contains_duration_without_global_dates_or_hp_fallback(self):
        policy = GracePeriod(True, True, 3)
        actual = rule(tariff_configuration=TariffConfiguration(Decimal('0.7'), Decimal('0.6'), None),
                      billing_modifiers=BillingModifiers(grace_period=policy,
                                                        recurring_additional_cost=Decimal('12.345678')))
        payload = BillingRuleSnapshot(actual).to_dict()
        self.assertEqual(payload['billing_modifiers']['grace_period'], {
            'enabled': True, 'without_discount': True, 'duration_months': 3})
        self.assertIsNone(payload['tariff_configuration']['tariff_hp'])
        self.assertNotIn('exclude_icms', {m.value for m in CalculationMethod})
        self.assertTrue(policy.requires_temporal_definition)
        with self.assertRaises(TypeError):
            GracePeriod(True, True, start=date(2026, 9, 1))

    def result(self, **values):
        return BillingCalculationResult(BillingCalculationContext(10, 20, 30, 40, '2030-08'),
                                        BillingRuleSnapshot(rule()), **values)

    def test_resolved_rule_and_scopes(self):
        for scope in ('company', 'client', 'consumer_unit'):
            actual = rule(source_scope=scope)
            self.assertEqual(actual.source_scope, BillingRuleScope(scope))
            self.assertEqual(actual.source_id, 10)
        self.assertEqual(rule().rule_version, '1')

    def test_only_documented_calculation_methods(self):
        self.assertEqual({m.value for m in CalculationMethod}, {
            'energia_compensada', 'economia_gerada', 'valor_total_fatura', 'tarifa_fixa',
            'tarifa_fixa_com_desconto', 'tarifa_especifica', 'energia_recebida'})
        for method in CalculationMethod:
            self.assertEqual(rule(calculation_method=method, manual_tariff=Decimal('1'),
                                  discount_type='percentage', discount_value=Decimal('10')).calculation_method, method)
        with self.assertRaises(ValueError):
            rule(calculation_method='inventado')

    def test_invoice_tariff_does_not_select_value(self):
        actual = rule(tariff_source='invoice')
        self.assertIs(actual.tariff_source, TariffSource.INVOICE)
        self.assertIsNone(actual.manual_tariff)
        self.assertIsNone(self.result().tariff_value)

    def test_manual_tariff_required_and_exact_precision(self):
        with self.assertRaises(ValueError):
            rule(tariff_source='manual')
        for tariff in (Decimal('0.123456'), Decimal('0.123456789'), Decimal('0.000000')):
            actual = rule(tariff_source='manual', manual_tariff=tariff)
            self.assertEqual(str(actual.manual_tariff), str(tariff))
            self.assertEqual(json_safe(actual)['manual_tariff'], str(tariff))

    def test_percentage_fixed_and_none_discounts(self):
        for kind in ('percentage', 'fixed'):
            with self.assertRaises(ValueError):
                rule(discount_type=kind)
            actual = rule(discount_type=kind, discount_value=Decimal('12.345678'))
            self.assertEqual(actual.discount_type, DiscountType(kind))
            self.assertEqual(actual.discount_value, Decimal('12.345678'))
        self.assertIsNone(rule().discount_value)

    def test_billing_modes_are_only_contract_not_auto_policy(self):
        for mode in BillingMode:
            self.assertEqual(rule(billing_mode=mode.value).billing_mode, mode)
        self.assertEqual(rule().billing_mode, BillingMode.AUTO)
        with self.assertRaises(ValueError):
            rule(billing_mode='invalid')

    def test_due_date_bases_and_signed_offsets(self):
        self.assertEqual({v.value for v in DueDateBasis}, {
            'invoice_due_date', 'invoice_issue_date', 'reading_date', 'calculation_date'})
        for basis in DueDateBasis:
            for offset in (-5, 0, 10):
                self.assertEqual(rule(due_date_basis=basis, due_date_offset_days=offset).due_date_offset_days, offset)
        for invalid in (True, 1.5, '2'):
            with self.assertRaises(TypeError):
                rule(due_date_offset_days=invalid)

    def test_interest_and_fine_are_decimal_not_default_zero(self):
        actual = rule(monthly_interest=Decimal('1.123456'), fine_percentage=Decimal('2.000001'))
        self.assertEqual(json_safe(actual)['monthly_interest'], '1.123456')
        self.assertEqual(json_safe(actual)['fine_percentage'], '2.000001')
        self.assertIsNone(rule().monthly_interest)
        self.assertIsNone(rule().fine_percentage)

    def test_all_decimal_fields_reject_float_string_nan(self):
        for name in ('manual_tariff', 'discount_value', 'monthly_interest', 'fine_percentage'):
            for value in (1.2, '1.2', True, Decimal('NaN'), Decimal('Infinity')):
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    rule(**{name: value})
        for name in ('energy_base_kwh', 'consumo_kwh', 'gd1_kwh', 'gd2_kwh', 'energia_compensada_kwh',
                     'tariff_value', 'gross_base', 'discount_amount', 'additions_amount', 'hub_amount'):
            with self.assertRaises(ValueError):
                self.result(**{name: 1.2})

    def test_tariff_bases_do_not_claim_gd_support(self):
        for basis in ('consumed', 'compensated', 'gd1', 'gd2'):
            self.assertEqual(rule(tariff_basis=basis).tariff_basis, TariffBasis(basis))
        self.assertIsNone(self.result().gd1_kwh)
        self.assertIsNone(self.result().gd2_kwh)
        with self.assertRaises(ValueError):
            rule(tariff_basis='anything')

    def test_documented_component_requires_index_without_selecting_it(self):
        actual = rule(tariff_basis='documented_component', energy_component_index=0)
        self.assertEqual(actual.energy_component_index, 0)
        with self.assertRaises(ValueError):
            rule(tariff_basis='documented_component')
        with self.assertRaises(ValueError):
            rule(energy_component_index=0)
        for invalid in (-1, True, '1'):
            with self.assertRaises(ValueError):
                rule(tariff_basis='documented_component', energy_component_index=invalid)

    def test_context_ids_competencia_and_explicit_timestamp(self):
        context = BillingCalculationContext(10, 20, 30, 40, '2030-08')
        self.assertIsNone(context.calculation_timestamp)
        timestamp = datetime(2030, 8, 1, 12)
        self.assertEqual(json_safe(replace(context, calculation_timestamp=timestamp))['calculation_timestamp'], timestamp.isoformat())
        for value in ('2030-13', '08/2030', '0000-01'):
            with self.assertRaises(ValueError):
                replace(context, competencia=value)
        for value in (0, -1, True, '10'):
            with self.assertRaises(ValueError):
                replace(context, empresa_id=value)

    def test_result_serializes_values_without_calculating_missing_fields(self):
        # Valores fornecidos ao DTO, não calculados por uma estratégia falsa.
        result = self.result(gross_base=Decimal('123.456789'), consumo_kwh=Decimal('20'),
                             gd1_kwh=Decimal('1'), gd2_kwh=Decimal('2'))
        payload = json.loads(json.dumps(result.to_dict(), allow_nan=False))
        self.assertEqual(payload['gross_base'], '123.456789')
        self.assertIsNone(payload['hub_amount'])
        self.assertIsNone(payload['energy_base_kwh'])
        self.assertIsNone(payload['discount_amount'])
        self.assertEqual(payload['calculation_version'], CALCULATION_ENGINE_VERSION)
        self.assertEqual(payload['rule_id'], payload['rule_snapshot']['rule_id'])
        self.assertEqual(payload['fatura_concessionaria_id'], 40)
        self.assertEqual((payload['gd1_kwh'], payload['gd2_kwh']), ('1', '2'))
        self.assertNotIn('gd_total', payload)

    def test_rule_snapshot_is_immutable_detached_and_serializable(self):
        actual = rule(manual_tariff=Decimal('0.123456'), metadata={'label': 'original'})
        snapshot = BillingRuleSnapshot(actual)
        actual.metadata['label'] = 'changed'
        detached = snapshot.to_dict()
        detached['metadata']['label'] = 'also changed'
        self.assertEqual(snapshot.to_dict()['metadata']['label'], 'original')
        self.assertEqual(snapshot.to_dict()['manual_tariff'], '0.123456')
        json.dumps(json_safe(snapshot), allow_nan=False)
        with self.assertRaises(FrozenInstanceError):
            snapshot.payload_json = '{}'

    def test_calculation_memory_nested_serialization_and_input_detached(self):
        memory = {'source': {'amount': Decimal('1.234567'), 'date': date(2030, 8, 1)},
                  'method': CalculationMethod.TARIFA_FIXA, 'unavailable': None}
        result = self.result(calculation_memory=memory)
        memory['source']['amount'] = Decimal('99')
        self.assertEqual(result.to_dict()['calculation_memory']['source']['amount'], '1.234567')
        self.assertEqual(result.to_dict()['calculation_memory']['source']['date'], '2030-08-01')
        with self.assertRaises(TypeError):
            self.result(calculation_memory={'nested': [1.5]})

    def test_financial_issues_do_not_accept_extraction_issues(self):
        issues = tuple(BillingCalculationIssue('code', severity, 'Message') for severity in BillingIssueSeverity)
        result = self.result(issues=issues)
        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(len(result.to_dict()['issues']), 3)
        with self.assertRaises(TypeError):
            self.result(issues=(ExtractionIssue('code', 'info', 'Not financial'),))

    def test_interfaces_are_abstract_and_have_no_real_strategy(self):
        for interface in (BillingCalculationEngine, BillingCalculationStrategy):
            with self.assertRaises(TypeError):
                interface()
        self.assertIn('calculate', BillingCalculationEngine.__abstractmethods__)
        self.assertIn('method', BillingCalculationStrategy.__abstractmethods__)

    def test_contracts_have_no_database_provider_or_parser_dependency(self):
        path = Path(__file__).resolve().parents[1] / 'services/billing_calculation_contracts.py'
        allowed = {'abc', 'copy', 'dataclasses', 'datetime', 'decimal', 'enum', 'json', 're',
                   'services.invoice_normalization_service'}
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if isinstance(node, ast.ImportFrom):
                self.assertIn(node.module, allowed)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertIn(alias.name, allowed)


if __name__ == '__main__':
    unittest.main()
