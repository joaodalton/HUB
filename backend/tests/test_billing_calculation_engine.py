"""C5.1: dados energéticos sintéticos; nenhuma alegação de suporte PDF GD."""
import ast
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal, localcontext, ROUND_DOWN
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.billing_calculation_contracts import (
    BillingCalculationContext, BillingModifiers, CalculationMemory, CalculationMethod, GracePeriod,
    ResolvedBillingRule, TariffConfiguration,
)
from services.billing_calculation_engine import (
    BillingCalculationEngine, BillingCalculationError, CompensatedEnergyBillingStrategy,
)
from services.invoice_compensation import BillingEnergyInput
from services.invoice_normalization_service import InvoiceNormalizer
from tests.test_invoice_compensation import parsed, found


class BillingCalculationEngineTest(unittest.TestCase):
    def setUp(self):
        self.context = BillingCalculationContext(1, 2, 4, 3, '2026-09')
        self.invoice = self.invoice_for('1000')
        self.rule = ResolvedBillingRule(
            1, 'Comercial', '7', 'company', 1, 'energia_compensada', 'manual',
            'none', 'compensated', 'auto', 'invoice_due_date', 0,
            manual_tariff=Decimal('0.70'), metadata={'assignment_id': '9'},
        )
        self.engine = BillingCalculationEngine()

    def invoice_for(self, energy):
        invoice = InvoiceNormalizer().normalize(
            parsed((('synthetic', '2026-06', energy, energy),)), empresa_id=1,
            client_id=2, fatura_concessionaria_id=3)
        return replace(invoice, consumer_unit_id=4)

    def calculate(self, **changes):
        return self.engine.calculate(**{'invoice': self.invoice, 'rule': self.rule,
                                       'context': self.context, **changes})

    def assert_block(self, code, **changes):
        with self.assertRaises(BillingCalculationError) as caught:
            self.calculate(**changes)
        self.assertEqual(caught.exception.code, code)

    def test_no_discount(self):
        result = self.calculate()
        self.assertEqual((result.gross_base, result.discount_amount, result.hub_amount),
                         (Decimal('700.00'), Decimal('0.00'), Decimal('700.00')))

    def test_twenty_percent(self):
        result = self.calculate(rule=replace(self.rule, discount_type='percentage', discount_value=Decimal('20')))
        self.assertEqual((result.gross_base, result.discount_amount, result.hub_amount),
                         (Decimal('700'), Decimal('140'), Decimal('560')))
        self.assertEqual(result.calculation_memory.effective_company_tariff, Decimal('0.56'))
        self.assertEqual(result.calculation_memory.discount_percentage, Decimal('20'))

    def test_decimal_precision_independent_of_global_context(self):
        invoice = self.invoice_for('333.333')
        rule = replace(self.rule, manual_tariff=Decimal('0.654321'), tariff_configuration=None)
        expected = self.calculate(invoice=invoice, rule=rule)
        with localcontext() as ctx:
            ctx.prec = 3
            ctx.rounding = ROUND_DOWN
            actual = self.calculate(invoice=invoice, rule=rule)
        self.assertEqual(expected, actual)
        self.assertEqual(actual.gross_base, Decimal('218.106781893'))
        self.assertEqual(actual.hub_amount, Decimal('218.11'))

    def test_round_only_final_half_up(self):
        result = self.calculate(invoice=self.invoice_for('1'), rule=replace(
            self.rule, manual_tariff=Decimal('0.025'), tariff_configuration=None,
            discount_type='percentage', discount_value=Decimal('20')))
        self.assertEqual(result.gross_base, Decimal('0.025'))
        self.assertEqual(result.discount_amount, Decimal('0.005'))
        self.assertEqual(result.hub_amount, Decimal('0.02'))
        half = self.calculate(invoice=self.invoice_for('1'), rule=replace(
            self.rule, manual_tariff=Decimal('0.005'), tariff_configuration=None))
        self.assertEqual(half.hub_amount, Decimal('0.01'))

    def test_invalid_energy_statuses(self):
        for status in ('AMBIGUOUS', 'MISSING', 'UNSUPPORTED'):
            with self.subTest(status=status):
                energy = replace(self.invoice.billing_energy_input, status=status,
                                 energia_compensada_cobravel_kwh=None)
                self.assert_block('required_energy_data_missing',
                                  invoice=replace(self.invoice, billing_energy_input=energy))

    def test_absent_energy_dto(self):
        self.assert_block('required_energy_data_missing', invoice=replace(self.invoice, billing_energy_input=None))

    def test_missing_tariff_does_not_use_document(self):
        rule = replace(self.rule, tariff_source='invoice', manual_tariff=None, tariff_configuration=None)
        self.assert_block('invalid_company_tariff', rule=rule)

    def test_negative_tariff(self):
        self.assert_block('invalid_company_tariff', rule=replace(
            self.rule, manual_tariff=Decimal('-0.70'), tariff_configuration=None))

    def test_negative_energy_rejected_without_abs(self):
        with self.assertRaises(ValueError):
            replace(self.invoice.billing_energy_input, energia_compensada_cobravel_kwh=Decimal('-1000'))
        # Defesa do motor se um produtor violar o contrato após a construção.
        with patch.object(BillingEnergyInput, 'require_valid', return_value=Decimal('-1000')):
            self.assert_block('invalid_energy_input')

    def test_hundred_percent(self):
        result = self.calculate(rule=replace(self.rule, discount_type='percentage', discount_value=Decimal('100')))
        self.assertEqual(result.hub_amount, Decimal('0.00'))
        self.assertEqual(result.calculation_memory.effective_company_tariff, Decimal('0'))

    def test_invalid_percentages(self):
        for percentage in ('-0.01', '100.01'):
            self.assert_block('invalid_discount', rule=replace(
                self.rule, discount_type='percentage', discount_value=Decimal(percentage)))

    def test_other_methods_never_fallback(self):
        for method in CalculationMethod:
            if method in (CalculationMethod.ENERGIA_COMPENSADA, CalculationMethod.TARIFA_FIXA,
                          CalculationMethod.TARIFA_ESPECIFICA):
                continue
            self.assert_block('unsupported_calculation_method', rule=replace(
                self.rule, calculation_method=method, discount_type='percentage', discount_value=Decimal('20')))

    def test_dispatch_uses_compensated_strategy(self):
        base = CompensatedEnergyBillingStrategy().calculate(
            invoice=self.invoice, rule=self.rule, context=self.context)
        with patch.object(CompensatedEnergyBillingStrategy, 'calculate', return_value=base) as calculate:
            self.assertEqual(self.calculate().gross_base, base.gross_base)
            calculate.assert_called_once_with(invoice=self.invoice, rule=self.rule, context=self.context)

    def test_deterministic_snapshot_memory_serialization(self):
        a, b = self.calculate(), self.calculate()
        self.assertEqual(a, b)
        self.assertEqual(a.to_dict(), b.to_dict())
        self.assertIsNone(a.context.calculation_timestamp)
        self.assertEqual(a.to_dict()['hub_amount'], '700.00')
        self.assertEqual(a.rule_snapshot.to_dict()['rule_version'], '7')
        self.assertEqual(a.calculation_version, '1.0')

    def test_snapshot_independent_and_frozen(self):
        result = self.calculate()
        self.rule.metadata['assignment_id'] = 'changed'
        self.assertEqual(result.rule_snapshot.to_dict()['metadata']['assignment_id'], '9')
        with self.assertRaises(FrozenInstanceError):
            self.rule.manual_tariff = Decimal('9')
        with self.assertRaises(FrozenInstanceError):
            result.calculation_memory.company_tariff_used = Decimal('9')

    def test_other_energy_and_concessionaire_amount_never_used(self):
        invoice = replace(self.invoice, campos={name: found(Decimal(value)) for name, value in (
            ('saldo_credito_kwh', '10000'), ('energia_injetada_kwh', '5000'),
            ('consumo_kwh', '1500'), ('valor_total_concessionaria', '800'))})
        result = self.calculate(invoice=invoice)
        self.assertEqual(result.energy_base_kwh, Decimal('1000'))
        self.assertEqual(result.gross_base, Decimal('700'))
        self.assertIsNone(result.calculation_memory.concessionaria_reference_tariff)

    def test_modifiers_and_hourly_tariffs_blocked(self):
        for modifiers in (BillingModifiers(icms_policy='exclude'),
                          BillingModifiers(exclude_tariff_flag=True),
                          BillingModifiers(grace_period=GracePeriod(True, True, 2)),
                          BillingModifiers(recurring_additional_cost=Decimal('0'))):
            self.assert_block('unsupported_billing_configuration', rule=replace(self.rule, billing_modifiers=modifiers))
        for hfp, hp in ((Decimal('0.7'), None), (None, Decimal('0.8'))):
            self.assert_block('unsupported_billing_configuration', rule=replace(self.rule,
                tariff_configuration=TariffConfiguration(Decimal('0.70'), hfp, hp)))

    def test_fixed_and_contradictory_discount_blocked(self):
        self.assert_block('unsupported_discount_type', rule=replace(self.rule, discount_type='fixed', discount_value=Decimal('10')))
        self.assert_block('invalid_discount', rule=replace(self.rule, discount_value=Decimal('10')))

    def test_context_mismatch_blocked(self):
        for name in ('empresa_id', 'client_id', 'consumer_unit_id', 'fatura_concessionaria_id'):
            self.assert_block('invalid_context', context=replace(self.context, **{name: 99}))
        self.assert_block('invalid_context', context=replace(self.context, competencia='2026-08'))
        self.assert_block('invalid_context', rule=replace(self.rule, source_id=99))
        self.assert_block('invalid_context', invoice=None)

    def test_zero_documental_is_valid_and_invoice_source_uses_company(self):
        self.assertEqual(self.calculate(invoice=self.invoice_for('0')).hub_amount, Decimal('0.00'))
        self.assertEqual(self.calculate(rule=replace(self.rule, tariff_source='invoice')).hub_amount, Decimal('700.00'))

    def test_invalid_numeric_types_and_new_memory_fields(self):
        for value in (None, 1.5, Decimal('NaN'), Decimal('Infinity')):
            with patch.object(BillingEnergyInput, 'require_valid', return_value=value):
                self.assert_block('invalid_energy_input')
        for name in ('discount_percentage', 'effective_company_tariff', 'net_amount_before_rounding'):
            with self.assertRaises(ValueError):
                CalculationMemory(**{name: 1.5})

    def test_engine_has_no_persistence_or_document_interpretation(self):
        path = Path(__file__).resolve().parents[1] / 'services/billing_calculation_engine.py'
        tree = ast.parse(path.read_text(encoding='utf-8'))
        forbidden = {'flask', 'sqlalchemy', 'models', 'pdfplumber', 're', 'requests'}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                self.assertNotIn(node.module.split('.')[0], forbidden)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotEqual(node.func.id, 'float')
        text = path.read_text(encoding='utf-8')
        for field in ('itens_documentais', 'energy_components', 'campos', 'TE', 'TUSD'):
            self.assertNotIn(f'.{field}', text)


if __name__ == '__main__':
    unittest.main()
