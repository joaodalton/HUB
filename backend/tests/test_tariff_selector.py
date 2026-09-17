import ast
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.billing_calculation_contracts import ResolvedBillingRule
from services.invoice_normalization_service import InvoiceNormalizer, json_safe
from services.invoice_parsers.schemas import ExtractedField, ExtractionIssue, ParsedInvoice, ParserIdentity
from services.tariff_selector import TariffSelector, TariffSelectionResult


def found(value, **kwargs):
    return ExtractedField('found', value, **kwargs)


def rule(**kwargs):
    values = dict(rule_id=1, rule_name='Teste', rule_version='1', source_scope='company',
                  source_id=1, calculation_method='energia_compensada', tariff_source='invoice',
                  discount_type='none', tariff_basis='consumed', billing_mode='auto',
                  due_date_basis='invoice_due_date', due_date_offset_days=0)
    return ResolvedBillingRule(**{**values, **kwargs})


def invoice():
    return InvoiceNormalizer().normalize(ParsedInvoice(
        ParserIdentity('test', '1'),
        itens=({'descricao_original': found('ENERGIA ELET CONSUMO'),
                'tarifa_unitaria': found(Decimal('0.734821'), confidence=Decimal('0.95'), source='p1:coluna tarifa'),
                'preco_unitario_com_tributos': found(Decimal('0.987654'), source='p1:coluna preço')},),
        energy_components=({'category': found('consumed'), 'unit': found('kWh'),
                            'amount_kwh': found(Decimal('12')), 'item_index': found(0)},),
    ))


class TariffSelectorTest(unittest.TestCase):
    def setUp(self):
        self.selector = TariffSelector()
        self.invoice = invoice()

    def codes(self, result):
        return {issue.code for issue in result.issues}

    def test_company_tariff_is_never_selected_as_documentary_reference(self):
        for value in (Decimal('0.734821'), Decimal('0.734821123456'), Decimal('0.000000')):
            configured = rule(tariff_source='manual', manual_tariff=value)
            result = self.selector.select(self.invoice, configured)
            self.assertIs(configured.tariff_configuration.company_tariff, value)
            self.assertIsNone(result.concessionaria_reference_tariff_kwh)
            self.assertEqual(result.source, 'invoice')
            self.assertEqual(result, self.selector.select(self.invoice, rule()))

    def test_legacy_manual_missing_is_structural_but_not_a_selector_input(self):
        with self.assertRaises(ValueError):
            rule(tariff_source='manual')
        damaged = rule(tariff_source='manual', manual_tariff=Decimal('1'))
        # Selector nem consulta a tarifa comercial, mesmo em DTO adulterado.
        for value in (None, 1.1):
            object.__setattr__(damaged, 'manual_tariff', value)
            result = self.selector.select(self.invoice, damaged)
            self.assertIsNone(result.value)
            self.assertEqual(result, self.selector.select(self.invoice, rule()))

    def test_invoice_candidates_distinguishable_and_auditable_but_policy_missing(self):
        result = self.selector.select(self.invoice, rule())
        self.assertIsNone(result.value)
        self.assertEqual(self.codes(result), {'ambiguous_document_tariff', 'tariff_reference_representation_required'})
        first, second = result.candidates
        self.assertEqual(first.value, Decimal('0.734821'))
        self.assertEqual(first.document_label, 'ENERGIA ELET CONSUMO')
        self.assertEqual(first.document_reference, 'itens_documentais[0].tarifa_unitaria')
        self.assertEqual(first.document_source, 'p1:coluna tarifa')
        self.assertEqual(first.confidence, Decimal('0.95'))
        self.assertEqual(second.document_field, 'preco_unitario_com_tributos')
        self.assertEqual(second.value, Decimal('0.987654'))

    def test_single_column_does_not_implicitly_choose_tax_policy(self):
        for field in ('tarifa_unitaria', 'preco_unitario_com_tributos'):
            row = self.invoice.tariffs_documented[0]
            doc = replace(self.invoice, tariffs_documented=({'item_index': row['item_index'], field: row[field]},))
            result = self.selector.select(doc, rule())
            self.assertIsNone(result.value)
            self.assertIn('tariff_reference_representation_required', self.codes(result))
            self.assertEqual(len(result.candidates), 1)

    def test_invoice_does_not_fall_back_to_manual_or_zero(self):
        doc = replace(self.invoice, tariffs_documented=())
        result = self.selector.select(doc, rule(manual_tariff=Decimal('123')))
        self.assertIsNone(result.value)
        self.assertIn('document_tariff_missing', self.codes(result))

    def test_failed_absent_and_ambiguous_are_distinct(self):
        for status, code in (('failed', 'unreadable_document_tariff'),
                             ('not_present', 'document_tariff_missing'),
                             ('ambiguous', 'ambiguous_document_tariff')):
            warning = ExtractionIssue('DOCUMENT_WARNING', 'warning', 'Revisar campo.')
            field = ExtractedField(status, warnings=(warning,))
            doc = replace(self.invoice, tariffs_documented=({'item_index': found(0), 'tarifa_unitaria': field},))
            result = self.selector.select(doc, rule())
            self.assertIsNone(result.value)
            self.assertIn(code, self.codes(result))
            self.assertEqual(result.candidates[0].status, status)
            self.assertEqual(result.warnings[0].code, 'DOCUMENT_WARNING')

    def test_unproven_bases_never_pick_consumption_tariff(self):
        for basis in ('gd1', 'gd2', 'compensated'):
            result = self.selector.select(self.invoice, rule(tariff_basis=basis))
            self.assertIsNone(result.value)
            self.assertIn('unsupported_tariff_basis', self.codes(result))
            self.assertEqual(result.candidates, ())

    def test_manual_selection_does_not_claim_energy_availability(self):
        result = self.selector.select(self.invoice, rule(tariff_source='manual',
            manual_tariff=Decimal('0.734821'), tariff_basis='gd1'))
        self.assertIsNone(result.value)
        self.assertIn('unsupported_tariff_basis', self.codes(result))
        self.assertEqual(result.basis, 'gd1')
        self.assertNotIn('energy_base_kwh', json_safe(result))

    def test_consumed_filters_category_and_does_not_reparse_labels(self):
        doc = deepcopy(self.invoice)
        doc.energy_components[0]['category'] = found('other')
        result = self.selector.select(doc, rule())
        self.assertIn('required_invoice_data_missing', self.codes(result))
        self.assertEqual(result.candidates, ())
        doc.energy_components[0]['category'] = ExtractedField('ambiguous', 'consumed')
        self.assertIn('ambiguous_tariff_basis', self.codes(self.selector.select(doc, rule())))

    def test_explicit_component_reference_is_not_item_position(self):
        doc = replace(self.invoice, energy_components=({'category': found('other')}, *self.invoice.energy_components))
        result = self.selector.select(doc, rule(tariff_basis='documented_component', energy_component_index=1))
        self.assertEqual(result.candidates[0].document_reference, 'itens_documentais[0].tarifa_unitaria')
        missing = self.selector.select(doc, rule(tariff_basis='documented_component', energy_component_index=5))
        self.assertIn('required_invoice_data_missing', self.codes(missing))

    def test_bad_item_references_and_component_data_block(self):
        for value in (-1, True, '0', 50):
            doc = deepcopy(self.invoice)
            doc.energy_components[0]['item_index'] = found(value)
            self.assertIn('invalid_document_reference', self.codes(self.selector.select(doc, rule())))
        for key, value in (('unit', found('UN')), ('amount_kwh', ExtractedField('failed'))):
            doc = deepcopy(self.invoice)
            doc.energy_components[0][key] = value
            self.assertIn('required_invoice_data_missing', self.codes(self.selector.select(doc, rule())))

    def test_duplicate_candidates_not_collapsed_even_with_equal_values(self):
        doc = replace(self.invoice, tariffs_documented=self.invoice.tariffs_documented * 2)
        result = self.selector.select(doc, rule())
        self.assertEqual(len(result.candidates), 4)
        self.assertIn('ambiguous_document_tariff', self.codes(result))
        self.assertIsNone(result.value)

    def test_no_float_in_result_or_serialization(self):
        for value in (1.2, Decimal('NaN'), '0.734821'):
            with self.assertRaises(ValueError):
                TariffSelectionResult(value, 'manual', 'consumed')
        payload = json_safe(self.selector.select(self.invoice, rule()))
        self.assertEqual(payload['candidates'][0]['value'], '0.734821')
        self.assertEqual(payload['candidates'][0]['confidence'], '0.95')

    def test_selector_pure_no_financial_operations_or_imports(self):
        before = json_safe(self.invoice)
        configured = rule(discount_type='percentage', discount_value=Decimal('99'))
        with patch('socket.socket.connect', side_effect=AssertionError('network')):
            self.assertEqual(self.selector.select(self.invoice, rule()), self.selector.select(self.invoice, configured))
        self.assertEqual(json_safe(self.invoice), before)
        path = Path(__file__).resolve().parents[1] / 'services/tariff_selector.py'
        allowed = {'dataclasses', 'decimal', 'services.billing_calculation_contracts',
                   'services.invoice_normalization_service', 'services.document_tariff_resolver'}
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if isinstance(node, ast.ImportFrom):
                self.assertIn(node.module, allowed)
            elif isinstance(node, ast.Import):
                for name in node.names:
                    self.assertIn(name.name, allowed)

    def test_existing_copel_fixture_composes_only_unit_tariffs(self):
        from services.invoice_parsers.copel import CopelDANF3EParser
        parsed = CopelDANF3EParser().parse((Path(__file__).parent / 'fixtures/invoices/copel/core_anon.pdf').read_bytes())
        normalized = InvoiceNormalizer().normalize(parsed)
        result = self.selector.select(normalized, rule())
        self.assertEqual(result.value, Decimal('0.358023'))
        self.assertEqual(len(result.candidates), 2)
        self.assertEqual({c.document_label for c in result.components},
                         {'ENERGIA ELET CONSUMO', 'ENERGIA ELET USO SISTEMA'})
        self.assertEqual([c.value for c in result.components], [Decimal('0.123456'), Decimal('0.234567')])
        self.assertEqual(result.issues, ())
        self.assertTrue(all(c.document_source and c.document_reference for c in result.components))

    def copel_invoice(self):
        from services.invoice_parsers.copel import CopelDANF3EParser
        return InvoiceNormalizer().normalize(CopelDANF3EParser().parse(
            (Path(__file__).parent / 'fixtures/invoices/copel/core_anon.pdf').read_bytes()))

    def test_copel_missing_failed_ambiguous_and_duplicates_block_without_zero(self):
        base = self.copel_invoice()
        for index in (0, 1):
            for status in ('not_present', 'failed', 'ambiguous'):
                doc = deepcopy(base)
                doc.tariffs_documented[index]['tarifa_unitaria'] = ExtractedField(status)
                result = self.selector.select(doc, rule(manual_tariff=Decimal('9')))
                self.assertIsNone(result.value)
                self.assertIn('concessionaire_tariff_ambiguous' if status == 'ambiguous'
                              else 'concessionaire_tariff_components_missing', self.codes(result))
            doc = replace(base, itens_documentais=(*base.itens_documentais, base.itens_documentais[index]))
            self.assertIn('concessionaire_tariff_ambiguous', self.codes(self.selector.select(doc, rule())))
        for change in (dict(tariffs_documented=()), dict(itens_documentais=())):
            self.assertIsNone(self.selector.select(replace(base, **change), rule()).value)

    def test_copel_sum_is_exact_under_low_decimal_precision_and_not_energy_dependent(self):
        from decimal import localcontext
        from services.billing_calculation_contracts import CalculationMemory
        doc = deepcopy(self.copel_invoice())
        a, b = Decimal('0.123456789012345678901234567890'), Decimal('0.000000000000000000000000000001')
        doc.tariffs_documented[0]['tarifa_unitaria'] = found(a, source='consumo')
        doc.tariffs_documented[1]['tarifa_unitaria'] = found(b, source='sistema')
        with localcontext() as context:
            context.prec = 6
            result = self.selector.select(replace(doc, energy_components=()), rule(tariff_basis='gd1'))
        self.assertEqual(result.value, Decimal('0.123456789012345678901234567891'))
        memory = CalculationMemory(concessionaria_reference_tariff=result.value,
            concessionaria_reference_components=tuple(json_safe(c) for c in result.components))
        self.assertEqual(json_safe(memory)['concessionaria_reference_components'][0]['value'], str(a))
        self.assertIsNone(memory.company_tariff_used)

    def test_composition_is_scoped_to_proven_layout_and_company_tariff_does_not_change_it(self):
        doc = self.copel_invoice()
        self.assertEqual(self.selector.select(doc, rule()), self.selector.select(doc,
            rule(tariff_source='manual', manual_tariff=Decimal('99'))))
        for identity in (ParserIdentity('other', '1', 'danf3e', 'DANF3EA4B-V1.06'),
                         ParserIdentity('copel', '99', 'danf3e', 'unknown')):
            result = self.selector.select(replace(doc, identity=identity), rule())
            self.assertIsNone(result.value)
            self.assertIn('tariff_reference_representation_required', self.codes(result))

    def test_copel_does_not_use_totals_taxed_prices_or_position_and_validates_units(self):
        doc = deepcopy(self.copel_invoice())
        for item in doc.itens_documentais[:2]:
            for name in ('valor', 'quantidade', 'preco_unitario_com_tributos'):
                item[name] = found(Decimal('999999'))
        reversed_rows = replace(doc, tariffs_documented=tuple(reversed(doc.tariffs_documented)))
        self.assertEqual(self.selector.select(reversed_rows, rule()).value, Decimal('0.358023'))
        doc.tariffs_documented[0]['tarifa_unitaria'] = found(Decimal('0'), source='zero documental')
        self.assertEqual(self.selector.select(doc, rule()).value, Decimal('0.234567'))
        doc.itens_documentais[1]['unidade'] = found('UN')
        self.assertIsNone(self.selector.select(doc, rule()).value)
        damaged = deepcopy(self.copel_invoice())
        damaged.tariffs_documented[1]['item_index'] = ExtractedField('ambiguous', 1)
        self.assertIn('concessionaire_tariff_ambiguous', self.codes(self.selector.select(damaged, rule())))


if __name__ == '__main__':
    unittest.main()
