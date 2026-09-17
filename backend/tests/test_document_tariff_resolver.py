"""C5.3A: fixtures estruturadas não comprovam novos layouts de PDF/GD."""
import ast
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal, localcontext
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.document_tariff_resolver import DocumentTariffResolver, ResolutionStatus
from services.invoice_normalization_service import InvoiceNormalizer, json_safe
from services.invoice_parsers.schemas import ExtractedField, ExtractionIssue, ParsedInvoice, ParserIdentity


def found(value, confidence=Decimal('0.95'), warnings=()):
    return ExtractedField('found', value, confidence, 'synthetic:document', warnings)


def compensation_invoice(events=(('event-1', '0.312345', '0.456789'),)):
    items, components = [], []
    for context, te, tusd in events:
        for kind, tariff in (('TE', te), ('TUSD', tusd)):
            index = len(items)
            items.append({
                'descricao_original': found(f'COMPENSACAO {kind}'),
                'descricao_normalizada': found(f'compensacao_{kind.lower()}'),
                'quantidade': found(Decimal('-100')), 'unidade': found('kWh'),
                'tarifa_unitaria': found(Decimal(tariff)), 'valor': found(Decimal('-10')),
            })
            components.append({
                'category': found('compensated'), 'unit': found('kWh'),
                'amount_kwh': found(Decimal('-100')), 'item_index': found(index),
                'origin': found('OUC'), 'period': found('MPT'),
                'compensation_context': found(context), 'tariff_component': found(kind),
            })
    parsed = ParsedInvoice(ParserIdentity('synthetic-domain-only', '1'), itens=tuple(items),
                           energy_components=tuple(components), compensation_supported=True)
    return InvoiceNormalizer().normalize(parsed)


def copel_invoice():
    from services.invoice_parsers.copel import CopelDANF3EParser
    path = Path(__file__).parent / 'fixtures/invoices/copel/core_anon.pdf'
    return InvoiceNormalizer().normalize(CopelDANF3EParser().parse(path.read_bytes()))


class DocumentTariffResolverTest(unittest.TestCase):
    def setUp(self):
        self.resolver = DocumentTariffResolver()

    def test_full_tariff_uses_proven_copel_components(self):
        result = self.resolver.resolve(copel_invoice()).full_tariff
        self.assertEqual((result.status, result.value), (ResolutionStatus.VALID, Decimal('0.358023')))
        self.assertEqual(result.source_item_indexes, (0, 1))

    def test_full_tariff_never_sums_line_totals(self):
        invoice = deepcopy(copel_invoice())
        for item in invoice.itens_documentais[:2]:
            item['valor'] = found(Decimal('999999'))
        self.assertEqual(self.resolver.resolve(invoice).full_tariff.value, Decimal('0.358023'))

    def test_decimal_sum_is_exact_under_low_global_precision(self):
        invoice = deepcopy(copel_invoice())
        a = Decimal('0.312345000000000000000000000001')
        b = Decimal('0.456789000000000000000000000002')
        invoice.tariffs_documented[0]['tarifa_unitaria'] = found(a)
        invoice.tariffs_documented[1]['tarifa_unitaria'] = found(b)
        with localcontext() as context:
            context.prec = 6
            value = self.resolver.resolve(invoice).full_tariff.value
        self.assertEqual(value, Decimal('0.769134000000000000000000000003'))

    def test_missing_full_component_never_returns_partial_value(self):
        invoice = deepcopy(copel_invoice())
        invoice.itens_documentais[1]['descricao_normalizada'] = ExtractedField('not_present')
        result = self.resolver.resolve(invoice).full_tariff
        self.assertEqual(result.status, ResolutionStatus.MISSING)
        self.assertIsNone(result.value)

    def test_compensation_tariff_uses_classified_te_tusd(self):
        result = self.resolver.resolve(compensation_invoice()).compensation_tariff
        self.assertEqual((result.status, result.value), (ResolutionStatus.VALID, Decimal('0.769134')))

    def test_missing_compensation_has_no_full_tariff_fallback(self):
        result = self.resolver.resolve(compensation_invoice(())).compensation_tariff
        self.assertEqual(result.status, ResolutionStatus.MISSING)
        self.assertIsNone(result.value)

    def test_multiple_full_candidates_are_ambiguous(self):
        invoice = copel_invoice()
        duplicate = deepcopy(invoice.itens_documentais[0])
        result = self.resolver.resolve(replace(invoice, itens_documentais=(*invoice.itens_documentais, duplicate))).full_tariff
        self.assertEqual(result.status, ResolutionStatus.AMBIGUOUS)
        self.assertIsNone(result.value)
        invoice = deepcopy(invoice)
        invoice.itens_documentais[0]['descricao_normalizada'] = ExtractedField('ambiguous', 'energia_elet_consumo')
        self.assertEqual(self.resolver.resolve(invoice).full_tariff.status, ResolutionStatus.AMBIGUOUS)

    def test_multiple_compensation_candidates_are_ambiguous(self):
        invoice = compensation_invoice((('a', '0.1', '0.2'), ('b', '0.3', '0.4')))
        result = self.resolver.resolve(invoice).compensation_tariff
        self.assertEqual(result.status, ResolutionStatus.AMBIGUOUS)
        self.assertIn('MULTIPLOS_CANDIDATOS_TARIFA_COMPENSACAO', {issue.code for issue in result.issues})
        invoice = deepcopy(invoice)
        invoice.tariffs_documented[3]['tarifa_unitaria'] = ExtractedField('not_present')
        self.assertEqual(self.resolver.resolve(invoice).compensation_tariff.status, ResolutionStatus.AMBIGUOUS)

    def test_compensation_source_indexes_are_preserved(self):
        result = self.resolver.resolve(compensation_invoice()).compensation_tariff
        self.assertEqual(result.source_item_indexes, (0, 1))
        self.assertEqual([item.document_reference for item in result.evidence],
                         ['itens_documentais[0].tarifa_unitaria', 'itens_documentais[1].tarifa_unitaria'])

    def test_confidence_is_the_lowest_source_confidence(self):
        invoice = deepcopy(compensation_invoice())
        tariff = invoice.tariffs_documented[1]['tarifa_unitaria']
        invoice.tariffs_documented[1]['tarifa_unitaria'] = replace(tariff, confidence=Decimal('0.41'))
        self.assertEqual(self.resolver.resolve(invoice).compensation_tariff.confidence, Decimal('0.41'))

    def test_source_warnings_remain_auditable(self):
        invoice = deepcopy(copel_invoice())
        warning = ExtractionIssue('LOW_OCR_CONFIDENCE', 'warning', 'Revisar leitura.')
        tariff = invoice.tariffs_documented[0]['tarifa_unitaria']
        invoice.tariffs_documented[0]['tarifa_unitaria'] = replace(tariff, warnings=(warning,))
        result = self.resolver.resolve(invoice).full_tariff
        self.assertIn('LOW_OCR_CONFIDENCE', {issue.code for issue in result.issues})
        self.assertEqual(result.evidence[0].warnings, (warning,))

    def test_separate_flag_marks_full_tariff_without_flag(self):
        result = self.resolver.resolve(copel_invoice()).full_tariff
        self.assertIs(result.includes_flag, False)

    def test_ambiguous_flag_is_unknown_and_reported(self):
        invoice = deepcopy(copel_invoice())
        flag = next(item for item in invoice.itens_documentais
                    if item['descricao_normalizada'].value == 'energia_cons_b_amarela')
        flag['descricao_normalizada'] = ExtractedField('ambiguous', 'energia_cons_b_amarela')
        result = self.resolver.resolve(invoice).full_tariff
        self.assertIsNone(result.includes_flag)
        self.assertIn('BANDEIRA_AMBIGUA', {issue.code for issue in result.issues})

    def test_explicit_taxed_variant_marks_selected_unit_tariff_without_taxes(self):
        result = self.resolver.resolve(copel_invoice()).full_tariff
        self.assertIs(result.with_taxes, False)

    def test_missing_taxed_variant_does_not_mean_without_taxes(self):
        invoice = deepcopy(copel_invoice())
        for row in invoice.tariffs_documented[:2]:
            row.pop('preco_unitario_com_tributos', None)
        self.assertIsNone(self.resolver.resolve(invoice).full_tariff.with_taxes)

    def test_tarifa_base_alone_does_not_become_full_tariff(self):
        parsed = ParsedInvoice(ParserIdentity('synthetic', '1'),
                               resumo={'tarifa_base': found(Decimal('0.99'))})
        result = self.resolver.resolve(InvoiceNormalizer().normalize(parsed)).full_tariff
        self.assertEqual(result.status, ResolutionStatus.MISSING)
        self.assertIsNone(result.value)

    def test_tariff_group_does_not_invent_a_value(self):
        parsed = ParsedInvoice(ParserIdentity('synthetic', '1'), classificacao={
            'grupo_tarifario': found('B'), 'subgrupo_tarifario': found('B1'),
            'modalidade_tarifaria': found('CONVENCIONAL'),
        })
        result = self.resolver.resolve(InvoiceNormalizer().normalize(parsed)).full_tariff
        self.assertEqual(result.status, ResolutionStatus.MISSING)
        self.assertIsNone(result.value)

    def test_resolver_is_pure_and_has_no_runtime_or_commercial_dependencies(self):
        invoice = copel_invoice()
        before = json_safe(invoice)
        self.resolver.resolve(invoice)
        self.assertEqual(json_safe(invoice), before)
        path = Path(__file__).resolve().parents[1] / 'services/document_tariff_resolver.py'
        tree = ast.parse(path.read_text(encoding='utf-8'))
        imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        self.assertFalse({'flask', 'sqlalchemy', 'services.billing_rule_resolver',
                          'services.billing_calculation_engine'} & imports)


if __name__ == '__main__':
    unittest.main()
