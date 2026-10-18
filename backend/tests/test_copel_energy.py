"""F6 parcial: fixture real sem GD; adversários não comprovam novos layouts."""
from dataclasses import asdict
from decimal import Decimal
import builtins
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.invoice_parsers.copel import CopelDANF3EParser, _decimal
from services.invoice_parsers.item_matcher import ItemMatcher, ItemMatcherRule
from services.invoice_parsers.schemas import ExtractedField, ParsedInvoice
try:
    from .fixtures.invoices.copel.build_fixture import ITEMS, make_pdf
except ImportError:
    from fixtures.invoices.copel.build_fixture import ITEMS, make_pdf


class CopelEnergyTest(unittest.TestCase):
    def test_c41_documentary_classification_is_not_a_tariff_or_cadastral_default(self):
        from services.invoice_normalization_service import InvoiceNormalizer
        parsed = self.parse()
        normalized = InvoiceNormalizer().normalize(parsed)
        for key, value in (('grupo_tarifario', 'B'), ('subgrupo_tarifario', 'B1'),
                           ('modalidade_tarifaria', 'CONVENCIONAL'),
                           ('classe_tarifaria', 'Residencial'),
                           ('subclasse_tarifaria', 'Residencial')):
            self.assertEqual(normalized.campos[key].value, value)
            self.assertTrue(normalized.campos[key].source)
        missing = InvoiceNormalizer().normalize(self.parse(omitted=('classification',)))
        self.assertIsNone(missing.campos['subgrupo_tarifario'].value)
        empty = InvoiceNormalizer().normalize(ParsedInvoice(parsed.identity))
        self.assertIsNone(empty.campos['grupo_tarifario'].value)
        self.assertIsNone(empty.campos['modalidade_tarifaria'].value)
        self.assertIsInstance(normalized.tariffs_documented[0]['tarifa_unitaria'].value, Decimal)

    def parse(self, **options):
        return CopelDANF3EParser().parse(make_pdf(**options))

    def sanitized_gd_components(self, case):
        folder = Path(__file__).parent / 'fixtures/invoices/copel'
        rows = json.loads((folder / 'gd_events_sanitized.json').read_text(encoding='utf-8'))[case]

        def found(value):
            return ExtractedField('found', value, Decimal('0.95'), 'sanitized:copel-real')

        items = tuple({
            'descricao_original': found(row['label']),
            'unidade': found('kWh'),
            'quantidade': found(Decimal(row['quantity_kwh'])),
            'preco_unitario_com_tributos': found(Decimal(row['taxed_unit_price'])),
            'tarifa_unitaria': found(Decimal(row['tariff_unit'])),
        } for row in rows)
        components, _, _ = CopelDANF3EParser()._energy(items, found(Decimal('0')))
        return rows, components

    def test_real_gd_labels_are_structured_without_collapsing_events(self):
        for case in ('own_and_ouc_gdii_2026_08', 'ouc_gdi_gdii_2026_09', 'ouc_gdii_2026_09'):
            rows, components = self.sanitized_gd_components(case)
            self.assertEqual(len(components), len(rows))
            for expected, actual in zip(rows, components):
                self.assertEqual(actual['category'].value, expected['category'])
                if expected['category'] in ('injected', 'compensated'):
                    self.assertEqual(actual['tariff_component'].value, expected['component'])
                    self.assertEqual(actual['gd_classification'].value, expected['gd'])
                    self.assertEqual(actual['credit_month'].value, expected['month'])
                if expected['category'] == 'compensated':
                    self.assertEqual(actual['origin'].value, 'OUC')
                    self.assertEqual(actual['period'].value, 'MPT')
                    self.assertEqual(actual['compensation_context'].value, 'energia_inj_ouc_mpt')

    def test_document_negative_decimal_is_preserved(self):
        self.assertEqual(_decimal('-352'), Decimal('-352'))

    def test_gdiii_document_label_reaches_unsupported_normalization(self):
        def found(value):
            return ExtractedField('found', value, Decimal('0.95'), 'synthetic:gdiii')

        items = tuple({
            'descricao_original': found(f'ENERGIA INJ. OUC MPT {kind} 08/2026 GDIII-III'),
            'unidade': found('kWh'), 'quantidade': found(Decimal('-10')),
            'tarifa_unitaria': found(Decimal('0.1')),
        } for kind in ('TE', 'TUSD'))
        parser = CopelDANF3EParser()
        components, energia, issues = parser._energy(items, found(Decimal('0')))
        self.assertEqual([row['gd_classification'].value for row in components], ['GD_III', 'GD_III'])
        from services.invoice_normalization_service import InvoiceNormalizer
        parsed = ParsedInvoice(parser.identity, itens=items, energy_components=components,
                               energia=energia, issues=issues, compensation_supported=True)
        self.assertEqual(InvoiceNormalizer().normalize(parsed).billing_energy_input.status, 'UNSUPPORTED')

    def test_fixture_expected_and_sources(self):
        folder = Path(__file__).parent / 'fixtures/invoices/copel'
        expected = json.loads((folder / 'core_anon.expected.json').read_text(encoding='utf-8'))
        parsed = CopelDANF3EParser().parse((folder / 'core_anon.pdf').read_bytes())
        self.assertEqual(len(parsed.energy_components), 3)
        for actual, wanted in zip(parsed.energy_components, expected['energy_components']):
            for key, value in wanted.items():
                self.assertEqual(str(actual[key].value), str(value))
                self.assertEqual(actual[key].status, 'found')
                self.assertTrue(actual[key].source)
        for key, wanted in expected['energia'].items():
            field = parsed.energia[key]
            self.assertEqual(field.status, wanted['status'])
            self.assertEqual(str(field.value) if field.value is not None else None, wanted['value'])

    def test_consumption_is_not_sum_or_choice_between_meter_and_items(self):
        parsed = self.parse()
        self.assertIs(parsed.energia['consumo_kwh'], parsed.resumo['consumo_kwh'])
        self.assertEqual(parsed.energia['consumo_kwh'].value, Decimal('225.123456'))
        self.assertEqual(parsed.energy_components[0]['amount_kwh'].value, Decimal('999.99'))
        self.assertIs(parsed.energy_components[0]['amount_kwh'], parsed.itens[0]['quantidade'])
        self.assertNotIn('gd_total', parsed.energia)

    def test_gd_and_credits_are_absent_not_zero_and_have_support_warning(self):
        parsed = self.parse()
        for key in ('gd1_kwh', 'gd2_kwh', 'energia_injetada_kwh', 'energia_compensada_kwh', 'saldo_creditos_kwh'):
            with self.subTest(key=key):
                field = parsed.energia[key]
                self.assertEqual(field.status, 'not_present')
                self.assertIsNone(field.value)
                self.assertIsNone(field.confidence)
                self.assertEqual(field.warnings[0].code, 'COPEL_ENERGY_NOT_SUPPORTED')

    def test_adversarial_labels_stay_individual_and_unclassified(self):
        # Não são fixtures GD reais: comprovam apenas recusa de inferência.
        labels = ('TESTE INJETADA', 'TESTE COMPENSADA', 'TESTE SALDO', 'TESTE GD-I', 'TESTE GD-II')
        rows = tuple((label, 'kWh', f'{i},123456', *ITEMS[0][3:]) for i, label in enumerate(labels, 1))
        parsed = self.parse(items=(*ITEMS, *rows))
        for index, component in enumerate(parsed.energy_components[-5:], 1):
            self.assertEqual(component['original_label'].value, labels[index - 1])
            self.assertEqual(component['amount_kwh'].value, Decimal(f'{index}.123456'))
            self.assertEqual(component['category'].status, 'ambiguous')
            self.assertEqual(component['category'].value, 'unclassified')
            self.assertEqual(component['category'].warnings[0].severity, 'info')
        self.assertTrue(all(v.value is None for k, v in parsed.energia.items() if k != 'consumo_kwh'))

    def test_duplicate_lines_preserved_not_collapsed(self):
        parsed = self.parse(items=(*ITEMS, ITEMS[0]))
        self.assertEqual(len(parsed.energy_components), 4)
        self.assertEqual([c['item_index'].value for c in parsed.energy_components], [0, 1, 2, 4])

    def test_matcher_only_observed_labels(self):
        rules = CopelDANF3EParser.energy_matcher.rules
        self.assertEqual([(r.mode, r.pattern, r.target, r.priority) for r in rules], [
            ('exact', ITEMS[0][0], 'consumed', 100),
            ('exact', ITEMS[1][0], 'other', 100),
            ('prefix', 'ENERGIA INJETADA ', 'injected', 100),
            ('prefix', 'ENERGIA INJ. OUC MPT ', 'compensated', 100),
            ('prefix', ITEMS[2][0], 'other', 100),
            ('exact', 'ENERGIA INJ. BAND. AMARELA TE', 'other', 100),
        ])

    def test_matcher_tie_is_ambiguous_not_first_wins(self):
        # Conflito de configuração, não alegação de um segundo layout real.
        matcher = ItemMatcher((ItemMatcherRule('exact', ITEMS[0][0], 'consumed', 100),
                               ItemMatcherRule('exact', ITEMS[0][0], 'other', 100)))
        with patch.object(CopelDANF3EParser, 'energy_matcher', matcher):
            component = self.parse().energy_components[0]
        self.assertEqual(component['category'].status, 'ambiguous')
        self.assertIsNone(component['category'].value)
        self.assertTrue(component['category'].warnings)

    def test_unit_missing_or_incompatible_not_converted_to_kwh(self):
        for unit in ('', 'UN'):
            rows = (ITEMS[0], (ITEMS[1][0], unit, *ITEMS[1][2:]), *ITEMS[2:])
            parsed = self.parse(items=rows)
            self.assertEqual(parsed.energy_components[1]['amount_kwh'].status, 'failed')
            self.assertEqual(parsed.itens[1]['quantidade'].value, Decimal('100'))
            self.assertTrue(any(i.code == 'COPEL_ENERGY_UNIT_UNSUPPORTED' for i in parsed.issues))

    def test_quantity_failed_and_missing_are_preserved(self):
        for quantity, status in (('ILEGIVEL', 'failed'), ('', 'not_present')):
            rows = (ITEMS[0], (*ITEMS[1][:2], quantity, *ITEMS[1][3:]), *ITEMS[2:])
            parsed = self.parse(items=rows)
            self.assertEqual(parsed.energy_components[1]['amount_kwh'].status, status)
            self.assertIsNone(parsed.energy_components[1]['amount_kwh'].value)

    def test_bank_compensation_is_not_energy(self):
        parsed = self.parse(duplicate='Ficha de Compensação')
        self.assertEqual(parsed.energia['energia_compensada_kwh'].status, 'not_present')
        self.assertEqual(len(parsed.energy_components), 3)

    def test_no_model_db_financial_or_network_dependencies(self):
        original = builtins.__import__

        def guarded(name, *args, **kwargs):
            if name.split('.')[0] in ('sqlalchemy', 'flask', 'models', 'extensions') or any(
                word in name for word in ('asaas', 'billing', 'normalizer', 'consumer_unit')
            ):
                raise AssertionError('Parser attempted domain dependency: ' + name)
            return original(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=guarded), patch('socket.socket.connect', side_effect=AssertionError('network')):
            parsed = self.parse()
        self.assertEqual(parsed.identity.parser_version, '1.3.0')
        self.assertEqual(parsed.identity.layout_version, 'DANF3EA4B-V1.06')
        self.assertNotIn('debito_automatico', parsed.energia)

    def test_components_decimal_no_float_and_schema_validation(self):
        parsed = self.parse()

        def check(value):
            self.assertNotIsInstance(value, float)
            if isinstance(value, dict):
                for child in value.values():
                    check(child)
            elif isinstance(value, (tuple, list)):
                for child in value:
                    check(child)
        check(asdict(parsed))
        for component in parsed.energy_components:
            self.assertIsInstance(component['amount_kwh'].value, Decimal)
        with self.assertRaises(TypeError):
            ParsedInvoice(parsed.identity, energy_components=({'amount_kwh': 1.1},))
        with self.assertRaises(TypeError):
            ExtractedField('found', 1.1)


if __name__ == '__main__':
    unittest.main()
