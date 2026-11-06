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


def compensation_invoice(events=(('event-1', '0.312345', '0.456789'),), separate_flag=False):
    items, components = [], []
    for event in events:
        if isinstance(event, dict):
            context, month, gd, quantity = (event[key] for key in ('context', 'month', 'gd', 'quantity'))
            tariffs = (('TE', event['te'], event.get('te_taxed')),
                       ('TUSD', event['tusd'], event.get('tusd_taxed')))
        else:
            context, te, tusd = event
            month, gd, quantity = None, 'UNKNOWN', '-100'
            tariffs = (('TE', te, None), ('TUSD', tusd, None))
        for kind, tariff, taxed in tariffs:
            index = len(items)
            item = {
                'descricao_original': found(f'COMPENSACAO {kind}'),
                'descricao_normalizada': found(f'compensacao_{kind.lower()}'),
                'quantidade': found(Decimal(quantity)), 'unidade': found('kWh'),
                'tarifa_unitaria': found(Decimal(tariff)), 'valor': found(Decimal('-10')),
            }
            if taxed is not None:
                item['preco_unitario_com_tributos'] = found(Decimal(taxed))
            items.append(item)
            component = {
                'category': found('compensated'), 'unit': found('kWh'),
                'amount_kwh': found(Decimal(quantity)), 'item_index': found(index),
                'origin': found('OUC'), 'period': found('MPT'),
                'tariff_component': found(kind),
                'gd_classification': found(gd),
            }
            if context is not None:
                component['compensation_context'] = found(context)
            if month is not None:
                component['credit_month'] = found(month)
            components.append(component)
    if separate_flag:
        items.append({
            'descricao_original': found('ENERGIA INJ. BAND. AMARELA TE'),
            'descricao_normalizada': found('energia_inj_band_amarela_te'),
            'quantidade': found(Decimal('-382')), 'unidade': found('kWh'),
            'tarifa_unitaria': found(Decimal('0.018850')),
            'preco_unitario_com_tributos': found(Decimal('0.018848')),
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

    def test_full_tariff_preserves_real_gd_invoice_composition(self):
        invoice = deepcopy(copel_invoice())
        invoice.tariffs_documented[0]['tarifa_unitaria'] = found(Decimal('0.310850'))
        invoice.tariffs_documented[1]['tarifa_unitaria'] = found(Decimal('0.457170'))
        self.assertEqual(self.resolver.resolve(invoice).full_tariff.value, Decimal('0.768020'))

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
        duplicate_identity = (
            {'context': 'same', 'month': '2026-08', 'gd': 'GD_II', 'quantity': '-352',
             'te': '0.310850', 'tusd': '0.328431'},
            {'context': 'same', 'month': '2026-08', 'gd': 'GD_II', 'quantity': '-352',
             'te': '0.310850', 'tusd': '0.328431'},
        )
        resolved = self.resolver.resolve(compensation_invoice(duplicate_identity))
        self.assertIsNone(resolved.compensation_tariff)
        self.assertEqual(resolved.compensation_tariff_events[0].status, ResolutionStatus.AMBIGUOUS)

    def test_incomplete_second_identity_blocks_scalar_from_valid_event(self):
        events = (
            {'context': 'valid', 'month': '2026-07', 'gd': 'GD_I', 'quantity': '-30',
             'te': '0.310850', 'tusd': '0.457170'},
            {'context': None, 'month': '2026-08', 'gd': 'GD_II', 'quantity': '-352',
             'te': '0.310850', 'tusd': '0.328431'},
        )
        resolved = self.resolver.resolve(compensation_invoice(events))
        self.assertIsNone(resolved.compensation_tariff)
        self.assertIn('COMPENSACAO_IDENTIDADE_INDEFINIDA', {issue.code for issue in resolved.issues})

    def test_gdi_and_gdii_have_distinct_valid_tariff_events_without_scalar(self):
        invoice = compensation_invoice((
            {'context': 'ouc', 'month': '2026-07', 'gd': 'GD_I', 'quantity': '-30',
             'te': '0.310850', 'tusd': '0.457170',
             'te_taxed': '0.310667', 'tusd_taxed': '0.457000'},
            {'context': 'ouc', 'month': '2026-08', 'gd': 'GD_II', 'quantity': '-352',
             'te': '0.310850', 'tusd': '0.328431',
             'te_taxed': '0.310824', 'tusd_taxed': '0.328409'},
        ), separate_flag=True)
        resolved = self.resolver.resolve(invoice)
        self.assertIsNone(resolved.compensation_tariff)
        self.assertEqual(len(resolved.compensation_tariff_events), 2)
        self.assertEqual([
            (event.identity.classificacao_gd, event.identity.mes_origem,
             event.identity.quantidade_kwh, event.combined_tariff, event.status)
            for event in resolved.compensation_tariff_events
        ], [
            ('GD_I', '2026-07', Decimal('30'), Decimal('0.768020'), ResolutionStatus.VALID),
            ('GD_II', '2026-08', Decimal('352'), Decimal('0.639281'), ResolutionStatus.VALID),
        ])
        self.assertEqual([event.source_item_indexes for event in resolved.compensation_tariff_events],
                         [(0, 1), (2, 3)])
        self.assertEqual([event.confidence for event in resolved.compensation_tariff_events],
                         [Decimal('0.95'), Decimal('0.95')])
        self.assertTrue(all(event.with_taxes is False for event in resolved.compensation_tariff_events))
        self.assertTrue(all(event.includes_flag is False for event in resolved.compensation_tariff_events))

    def test_equivalent_event_tariffs_keep_safe_scalar_compatibility(self):
        common = (
            {'context': 'ouc', 'month': '2026-07', 'gd': 'GD_I', 'quantity': '-30',
             'te': '0.310850', 'tusd': '0.457170'},
            {'context': 'ouc', 'month': '2026-08', 'gd': 'GD_II', 'quantity': '-352',
             'te': '0.310850', 'tusd': '0.457170'},
        )
        resolved = self.resolver.resolve(compensation_invoice(common))
        self.assertEqual(resolved.compensation_tariff.value, Decimal('0.768020'))
        self.assertEqual(resolved.compensation_tariff.status, ResolutionStatus.VALID)

    def test_equal_combined_value_with_different_components_has_no_scalar(self):
        events = (
            {'context': 'ouc', 'month': '2026-07', 'gd': 'GD_I', 'quantity': '-30',
             'te': '0.300000', 'tusd': '0.400000'},
            {'context': 'ouc', 'month': '2026-08', 'gd': 'GD_II', 'quantity': '-352',
             'te': '0.200000', 'tusd': '0.500000'},
        )
        self.assertIsNone(self.resolver.resolve(compensation_invoice(events)).compensation_tariff)

    def test_taxed_price_never_replaces_event_unit_tariff(self):
        event = ({'context': 'ouc', 'month': '2026-08', 'gd': 'GD_II', 'quantity': '-352',
                  'te': '0.310850', 'tusd': '0.328431',
                  'te_taxed': '9.000000', 'tusd_taxed': '8.000000'},)
        resolved = self.resolver.resolve(compensation_invoice(event)).compensation_tariff_events[0]
        self.assertEqual((resolved.te_tariff, resolved.tusd_tariff, resolved.combined_tariff),
                         (Decimal('0.310850'), Decimal('0.328431'), Decimal('0.639281')))

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
