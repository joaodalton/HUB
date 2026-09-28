"""C5.4: valores sinteticos comprovam ordem, nao formulas tributarias reais."""
from dataclasses import replace
from decimal import Decimal, localcontext, ROUND_DOWN
import unittest

from services.billing_calculation_contracts import BillingCalculationContext, BillingModifiers
from services.billing_calculation_engine import BillingCalculationEngine, BillingCalculationError
from services.commercial_deduction_resolver import DocumentDeductionEvidence
from services.commercial_tariff_selector import CommercialTariffSelector
from services.document_tariff_resolver import DocumentTariffResolver
from tests.test_commercial_tariff_selector import EVENTS, rule
from tests.test_document_tariff_resolver import compensation_invoice, found
from tests.test_commercial_deduction_resolver import tax_row


class BillingDeductionsTest(unittest.TestCase):
    def setUp(self):
        self.context = BillingCalculationContext(1, 2, 4, 3, '2026-09')
        self.engine = BillingCalculationEngine()

    def invoice(self, events=None):
        events = events or ({**EVENTS[1], 'quantity': '-1000'},)
        invoice = compensation_invoice(events)
        return replace(invoice, empresa_id=1, client_id=2, consumer_unit_id=4,
                       billing_energy_input=replace(invoice.billing_energy_input,
                           competencia='2026-09', fatura_concessionaria_id=3))

    def configured(self, method='tarifa_fixa', tariff='0.90', pis=True, fio=True):
        return replace(rule(method, tariff), discount_type='percentage', discount_value=Decimal('20'),
                       billing_modifiers=BillingModifiers(exclude_pis_cofins=pis, exclude_gdii_fio_b=fio))

    def evidence(self, invoice, values=('10', '20', '0.20')):
        items = list(invoice.itens_documentais)
        evidence = []
        event = invoice.billing_energy_input.compensacoes[-1]
        for kind, value in zip(('PIS', 'COFINS'), values):
            amount = found(Decimal(value))
            evidence.append(DocumentDeductionEvidence(kind, event, amount, (len(items),),
                f'itens_documentais[{len(items)}].valor', 3, '2026-09'))
            items.append(tax_row(kind, event, amount))
        tusd = next(c for c in event.componentes if c.tipo == 'TUSD')
        tariff = found(Decimal(values[2]))
        index = tusd.energy_evidence['item_index'].value
        items[index]['tusd_fio_b_unit_tariff'] = tariff
        tusd.documento['tusd_fio_b_unit_tariff'] = tariff
        return replace(invoice, itens_documentais=tuple(items)), tuple(evidence)

    def calculate(self, invoice, selected_rule, **kwargs):
        return self.engine.calculate(invoice=invoice, rule=selected_rule, context=self.context, **kwargs)

    def test_canonical_order_and_complete_audit(self):
        invoice, evidence = self.evidence(self.invoice())
        result = self.calculate(invoice, self.configured(), deduction_evidence=evidence)
        self.assertEqual((result.gross_base, result.discount_amount, result.hub_amount),
                         (Decimal('900'), Decimal('180'), Decimal('570.00')))
        memory = result.calculation_memory
        self.assertEqual((memory.post_discount_amount, memory.post_pis_cofins_amount,
                          memory.net_amount_before_rounding), (Decimal('720'), Decimal('690'), Decimal('570')))
        self.assertEqual((memory.pis_amount, memory.cofins_amount, memory.fio_b_amount),
                         (Decimal('10'), Decimal('20'), Decimal('120')))
        self.assertTrue(result.rule_snapshot.to_dict()['billing_modifiers']['exclude_gdii_fio_b'])
        self.assertTrue(memory.exclude_gdii_fio_b)

    def test_disabled_deductions_preserve_fixed_specific(self):
        for method, expected in (('tarifa_fixa', '560.00'), ('tarifa_especifica', '700.00')):
            result = self.calculate(self.invoice(), self.configured(method, '0.70', False, None))
            self.assertEqual(result.hub_amount, Decimal(expected))
            self.assertEqual(result.calculation_memory.pis_cofins_amount, Decimal(0))
            self.assertEqual(result.calculation_memory.fio_b_amount, Decimal(0))

    def test_fixed_specific_deductions_follow_discount(self):
        invoice, evidence = self.evidence(self.invoice())
        for method, expected in (('tarifa_fixa', '410.00'), ('tarifa_especifica', '550.00')):
            result = self.calculate(invoice, self.configured(method, '0.70'), deduction_evidence=evidence)
            self.assertEqual(result.hub_amount, Decimal(expected))

    def test_enabled_missing_blocks_amount_and_preserves_base(self):
        result = self.calculate(self.invoice(), self.configured())
        self.assertEqual(result.resolution_status, 'MISSING')
        self.assertIsNone(result.hub_amount)
        self.assertEqual(result.calculation_memory.post_discount_amount, Decimal('720'))
        self.assertIsNone(result.calculation_memory.pis_cofins_amount)
        self.assertIsNone(result.calculation_memory.net_amount_before_rounding)

    def test_excess_deductions_clamp_zero_with_issue(self):
        invoice, evidence = self.evidence(self.invoice(), ('500', '400', '0.20'))
        result = self.calculate(invoice, self.configured(), deduction_evidence=evidence)
        self.assertEqual(result.hub_amount, Decimal('0.00'))
        self.assertEqual(result.calculation_memory.net_amount_before_rounding, Decimal('-300'))
        self.assertIn('DEDUCOES_SUPERAM_VALOR_COBRAVEL', [i.code for i in result.issues])

    def test_precision_and_only_final_rounding(self):
        invoice = self.invoice(({**EVENTS[1], 'quantity': '-1'},))
        invoice, evidence = self.evidence(invoice, ('0.001', '0.001', '0.001'))
        selected_rule = self.configured(tariff='0.025')
        expected = self.calculate(invoice, selected_rule, deduction_evidence=evidence)
        with localcontext() as ctx:
            ctx.prec = 2
            ctx.rounding = ROUND_DOWN
            actual = self.calculate(invoice, selected_rule, deduction_evidence=evidence)
        self.assertEqual(actual, expected)
        self.assertEqual(actual.calculation_memory.net_amount_before_rounding, Decimal('0.0174'))
        self.assertEqual(actual.hub_amount, Decimal('0.02'))

    def test_event_tariffs_remain_separate_and_no_average(self):
        invoice = self.invoice(EVENTS)
        selected_rule = rule(icms='exclude')
        selected = CommercialTariffSelector().select(DocumentTariffResolver().resolve(invoice), selected_rule)
        result = self.calculate(invoice, selected_rule, selected_tariffs=selected)
        self.assertEqual(result.gross_base, Decimal('248.067512'))
        self.assertIsNone(result.tariff_value)
        rows = result.calculation_memory.event_calculations
        self.assertEqual([r['quantity_kwh'] for r in rows], [Decimal('30'), Decimal('352')])

    def test_specific_gdii_deduction_keeps_event_link(self):
        invoice, evidence = self.evidence(self.invoice(EVENTS))
        selected_rule = replace(rule(icms='exclude'), billing_modifiers=BillingModifiers(
            icms_policy='exclude', exclude_gdii_fio_b=True))
        selected = CommercialTariffSelector().select(DocumentTariffResolver().resolve(invoice), selected_rule)
        result = self.calculate(invoice, selected_rule, selected_tariffs=selected, deduction_evidence=evidence)
        components = result.calculation_memory.fio_b_components
        self.assertEqual([row['status'] for row in components], ['NOT_APPLICABLE', 'RESOLVED'])
        self.assertEqual(components[1]['event']['classificacao_gd'], 'GD_II')
        self.assertEqual(result.hub_amount, Decimal('205.83'))

    def test_forged_selection_missing_duplicate_and_snapshot_rejected(self):
        invoice = self.invoice(EVENTS)
        selected_rule = rule(icms='exclude')
        selected = CommercialTariffSelector().select(DocumentTariffResolver().resolve(invoice), selected_rule)
        variants = (selected[:1], selected + selected[:1],
                    (replace(selected[0], selected_tariff=Decimal('9')), selected[1]))
        for selections in variants:
            with self.assertRaises(BillingCalculationError):
                self.calculate(invoice, selected_rule, selected_tariffs=selections)
        with self.assertRaises(BillingCalculationError):
            self.calculate(invoice, replace(selected_rule, rule_version='99'), selected_tariffs=selected)

    def test_invalid_selection_returns_blocked_audit(self):
        invoice = self.invoice(EVENTS)
        selected_rule = rule(icms=None)
        selected = CommercialTariffSelector().select(DocumentTariffResolver().resolve(invoice), selected_rule)
        result = self.calculate(invoice, selected_rule, selected_tariffs=selected)
        self.assertEqual(result.resolution_status, 'UNSUPPORTED')
        self.assertIsNone(result.hub_amount)
        self.assertEqual(len(result.calculation_memory.event_calculations), 2)

    def test_tax_document_audit_does_not_deduct_aggregate_values(self):
        invoice = self.invoice()
        invoice = replace(invoice, tributos=tuple({
            'tributo': found(kind), 'base_calculo': found(Decimal('200')),
            'aliquota': found(Decimal(rate)), 'valor': found(Decimal(amount))}
            for kind, rate, amount in (('PIS', '0.63', '1.26'), ('COFINS', '2.89', '5.78'))))
        result = self.calculate(invoice, self.configured(pis=False, fio=False))
        self.assertEqual(result.hub_amount, Decimal('720.00'))
        audit = result.calculation_memory.document_taxes
        self.assertEqual(audit['pis']['amount'], Decimal('1.26'))
        self.assertEqual(audit['pis']['rate'], Decimal('0.63'))
        self.assertEqual(audit['cofins']['amount'], Decimal('5.78'))
        self.assertEqual(audit['cofins']['base'], Decimal('200'))
        self.assertEqual(audit['cofins']['source'], 'DOCUMENT')
        self.assertEqual(audit['cofins']['status'], 'RESOLVED')
        blocked = self.calculate(invoice, self.configured(pis=True, fio=False))
        self.assertIsNone(blocked.hub_amount)

    def test_absent_taxes_are_missing_data_not_zero(self):
        result = self.calculate(self.invoice(), self.configured(pis=False, fio=False))
        for component in result.calculation_memory.document_taxes.values():
            self.assertEqual(component['status'], 'MISSING_DATA')
            self.assertIsNone(component['amount'])

    def test_fio_b_formula_integrates_after_discount(self):
        from tests.test_fio_b_resolver import invoice as fio_invoice
        invoice = replace(fio_invoice(), empresa_id=1, client_id=2, consumer_unit_id=4)
        result = self.calculate(invoice, self.configured(pis=False))
        self.assertEqual(result.hub_amount, Decimal('600.00'))
        component = result.calculation_memory.fio_b_components[0]
        self.assertEqual(component['status'], 'RESOLVED')
        self.assertEqual(component['amount'], '120.0000')

    def test_aneel_regulatory_fio_b_integrates_without_runtime_tariff_input(self):
        from tests.test_fio_b_resolver import invoice as fio_invoice
        invoice = replace(fio_invoice(tariff=None), empresa_id=1, client_id=2, consumer_unit_id=4)
        invoice.campos.update({name: found(value) for name, value in (
            ('concessionaria', 'Copel'), ('subgrupo_tarifario', 'B1'),
            ('modalidade_tarifaria', 'CONVENCIONAL'), ('classe_tarifaria', 'Residencial'),
            ('subclasse_tarifaria', 'Residencial'))})
        result = self.calculate(invoice, self.configured(pis=False))
        self.assertEqual(result.hub_amount, Decimal('591.28'))
        component = result.calculation_memory.fio_b_components[0]
        self.assertEqual((component['status'], component['tariff_source']), ('RESOLVED', 'REGULATORY'))
        self.assertEqual(Decimal(component['amount']), Decimal('128.721360224400006000'))

    def test_gdi_does_not_require_fio_b_tariff(self):
        invoice = self.invoice(({**EVENTS[0], 'quantity': '-1000'},))
        result = self.calculate(invoice, self.configured(pis=False))
        self.assertEqual(result.hub_amount, Decimal('720.00'))
        self.assertEqual(result.calculation_memory.fio_b_components[0]['status'], 'NOT_APPLICABLE')

    def test_gdiii_is_unsupported_with_audit(self):
        from tests.test_fio_b_resolver import invoice as fio_invoice
        invoice = replace(fio_invoice(gd='GD_III'), empresa_id=1, client_id=2, consumer_unit_id=4)
        result = self.calculate(invoice, self.configured(pis=False))
        self.assertEqual(result.resolution_status, 'UNSUPPORTED')
        self.assertIsNone(result.hub_amount)
        self.assertEqual(result.calculation_memory.fio_b_components[0]['status'], 'UNSUPPORTED')

    def test_2029_and_legacy_monetary_evidence_cannot_skip_regulatory_rule(self):
        from tests.test_fio_b_resolver import invoice as fio_invoice
        invoice = replace(fio_invoice(month='2029-09'), empresa_id=1, client_id=2, consumer_unit_id=4)
        context = replace(self.context, competencia='2029-09')
        result = self.engine.calculate(invoice=invoice, rule=self.configured(pis=False), context=context)
        self.assertEqual(result.resolution_status, 'UNSUPPORTED')
        self.assertIsNone(result.hub_amount)

    def test_missing_tax_base_rate_and_duplicate_rows_remain_explicit(self):
        invoice = self.invoice()
        row = {'tributo': found('PIS/PASEP'), 'valor': found(Decimal('-1.00'))}
        invoice = replace(invoice, tributos=(row,))
        result = self.calculate(invoice, self.configured(pis=False, fio=False))
        pis = result.calculation_memory.document_taxes['pis']
        self.assertEqual(pis['amount'], Decimal('-1.00'))
        self.assertIsNone(pis['base'])
        self.assertIsNone(pis['rate'])
        result = self.calculate(replace(invoice, tributos=(row, row)), self.configured(pis=False, fio=False))
        self.assertEqual(result.calculation_memory.document_taxes['pis']['status'], 'AMBIGUOUS')
        self.assertIsNone(result.calculation_memory.document_taxes['pis']['amount'])


if __name__ == '__main__':
    unittest.main()
