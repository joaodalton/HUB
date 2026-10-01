from dataclasses import asdict
from decimal import Decimal
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.invoice_parsers.copel import CopelDANF3EParser
from services.invoice_parsers.item_matcher import ItemMatcher, ItemMatcherRule
from services.invoice_compensation import EnergyStatus
from services.invoice_normalization_service import InvoiceNormalizer
try:
    from .fixtures.invoices.copel.build_fixture import ITEMS, TAXES, make_pdf
except ImportError:
    from fixtures.invoices.copel.build_fixture import ITEMS, TAXES, make_pdf


class CopelDeepTest(unittest.TestCase):
    def parse(self, **options):
        return CopelDANF3EParser().parse(make_pdf(**options))

    def test_all_deep_fields_match_expected(self):
        folder = Path(__file__).parent / 'fixtures/invoices/copel'
        expected = json.loads((folder / 'core_anon.expected.json').read_text(encoding='utf-8'))
        parsed = CopelDANF3EParser().parse((folder / 'core_anon.pdf').read_bytes())
        for section in ('itens', 'tributos', 'historico_consumo', 'medidor'):
            actual_rows = (parsed.medidor,) if section == 'medidor' else getattr(parsed, section)
            expected_rows = (expected[section],) if section == 'medidor' else expected[section]
            self.assertEqual(len(actual_rows), len(expected_rows))
            for actual, wanted in zip(actual_rows, expected_rows):
                for key, value in wanted.items():
                    with self.subTest(section=section, key=key):
                        self.assertEqual(actual[key].value if value is None else str(actual[key].value), value)
                        self.assertEqual(actual[key].status, 'not_present' if value is None else 'found')
                        self.assertTrue(actual[key].source)

    def test_matcher_exact(self):
        matcher = ItemMatcher((ItemMatcherRule('exact', 'ENERGIA', 'label'),))
        self.assertEqual(matcher.match('ENERGIA'), ('label',))
        self.assertEqual(matcher.match('ENERGIA OUTRA'), ())

    def test_matcher_prefix(self):
        self.assertEqual(ItemMatcher((ItemMatcherRule('prefix', 'ENERGIA', 'label'),)).match('ENERGIA OUTRA'), ('label',))

    def test_matcher_contains(self):
        self.assertEqual(ItemMatcher((ItemMatcherRule('contains', 'ELET', 'label'),)).match('ENERGIA ELET CONSUMO'), ('label',))

    def test_matcher_regex(self):
        self.assertEqual(ItemMatcher((ItemMatcherRule('regex', r'^ENERGIA\s+ELET', 'label'),)).match('ENERGIA  ELET'), ('label',))

    def test_matcher_priority_and_ties(self):
        rules = (ItemMatcherRule('contains', 'ENERGIA', 'generic', 1), ItemMatcherRule('exact', 'ENERGIA ELET', 'specific', 100))
        for ordered in (rules, tuple(reversed(rules))):
            self.assertEqual(ItemMatcher(ordered).match('ENERGIA ELET'), ('specific',))
        tied = (ItemMatcherRule('exact', 'X', 'a', 1), ItemMatcherRule('exact', 'X', 'b', 1))
        self.assertEqual(ItemMatcher(tied).match('X'), ('a', 'b'))

    def test_matcher_invalid_configuration(self):
        with self.assertRaises(ValueError):
            ItemMatcherRule('invalid', 'x', 'y')
        with self.assertRaises(Exception):
            ItemMatcherRule('regex', '[', 'y')

    def test_multiple_items_original_descriptions_and_decimal_tariffs(self):
        parsed = self.parse()
        self.assertEqual([r['descricao_original'].value for r in parsed.itens], [r[0] for r in ITEMS])
        for row in parsed.itens:
            self.assertIsInstance(row['preco_unitario_com_tributos'].value, Decimal)
            self.assertEqual(row['preco_unitario_com_tributos'].value.as_tuple().exponent, -6)
        self.assertEqual(str(parsed.itens[0]['tarifa_unitaria'].value), '0.123456')
        self.assertEqual(parsed.itens[3]['quantidade'].status, 'not_present')

    def test_anonymous_second_copy_keeps_only_four_financial_items_and_no_compensation(self):
        parsed = self.parse(
            changes={'address': 'Endereço: Endereco Ficticio, 999 - Complemento Preservado'},
            # Linha fora da tabela que reproduz o falso candidato documental da segunda via.
            pre_item_lines=('Segunda ViaCONSUMO FATURADO          UN       1,00',),
        )
        self.assertEqual([row['descricao_original'].value for row in parsed.itens],
                         [row[0] for row in ITEMS])
        self.assertEqual(parsed.titular['complemento'].value, 'Complemento Preservado')
        self.assertEqual(parsed.titular['cpf_cnpj'].status, 'not_present')
        self.assertIn('COPEL_CPF_MASKED', {issue.code for issue in parsed.titular['cpf_cnpj'].warnings})
        public_lighting = parsed.itens[-1]
        self.assertEqual(public_lighting['quantidade'].warnings, ())
        self.assertEqual(public_lighting['tarifa_unitaria'].warnings, ())
        self.assertEqual(parsed.resumo['consumo_kwh'].value, Decimal('225.123456'))
        self.assertEqual([row['tarifa_unitaria'].value for row in parsed.itens[:3]],
                         [Decimal('0.123456'), Decimal('0.234567'), Decimal('0.001234')])
        self.assertEqual([row['tributo'].value for row in parsed.tributos], ['ICMS', 'COFINS', 'PIS'])
        self.assertEqual(parsed.resumo['valor_total_concessionaria'].value, Decimal('1234.567890'))
        normalized = InvoiceNormalizer().normalize(parsed)
        self.assertEqual(normalized.status_normalizacao, 'normalizada')
        self.assertEqual(normalized.billing_energy_input.status, EnergyStatus.UNSUPPORTED)
        self.assertIsNone(normalized.billing_energy_input.energia_compensada_cobravel_kwh)

    def test_no_float_anywhere_in_parsed_invoice(self):
        def check(value):
            self.assertNotIsInstance(value, float)
            if isinstance(value, dict):
                for child in value.values():
                    check(child)
            elif isinstance(value, (list, tuple)):
                for child in value:
                    check(child)
        check(asdict(self.parse()))

    def test_tax_values_are_documental_not_computed(self):
        parsed = self.parse(taxes=(('ICMS', '100,00', '19%', '7,77'), *TAXES[1:]))
        self.assertEqual([t['tributo'].value for t in parsed.tributos], ['ICMS', 'COFINS', 'PIS'])
        self.assertEqual(parsed.tributos[0]['valor'].value, Decimal('7.77'))
        self.assertEqual(parsed.tributos[0]['aliquota'].value, Decimal('19'))

    def test_tax_invalid_value_is_failed(self):
        parsed = self.parse(taxes=(('ICMS', '100,00', 'ILEGIVEL%', '7,77'),))
        self.assertEqual(parsed.tributos[0]['aliquota'].status, 'failed')

    def test_history_keeps_months_and_does_not_infer_gaps(self):
        parsed = self.parse(history=(('AGO30', '101,123456', ''), ('JUN30', '99', '30')))
        self.assertEqual([r['competencia'].value for r in parsed.historico_consumo], ['AGO30', 'JUN30'])
        self.assertEqual(parsed.historico_consumo[0]['consumo_kwh'].value, Decimal('101.123456'))
        self.assertEqual(parsed.historico_consumo[0]['dias_faturados'].status, 'not_present')
        self.assertEqual(self.parse(history=False).historico_consumo, ())

    def test_meter_preserves_indices_and_reuses_consumption(self):
        parsed = self.parse()
        self.assertEqual(parsed.medidor['numero'].value, '0000000001')
        self.assertEqual(parsed.medidor['leitura_anterior'].value, Decimal('10000'))
        self.assertEqual(parsed.medidor['leitura_atual'].value, Decimal('10225'))
        self.assertEqual(parsed.medidor['constante'].value, Decimal('1'))
        self.assertIs(parsed.medidor['consumo_kwh'], parsed.resumo['consumo_kwh'])
        self.assertNotEqual(parsed.medidor['consumo_kwh'].value, parsed.itens[0]['quantidade'].value)

    def test_unknown_items_including_first_are_preserved(self):
        rows = (('ITEM DESCONHECIDO', *ITEMS[0][1:]), *ITEMS[1:])
        parsed = self.parse(items=rows)
        self.assertEqual(len(parsed.itens), 4)
        self.assertEqual(parsed.itens[0]['descricao_original'].value, 'ITEM DESCONHECIDO')
        self.assertTrue(any(i.code == 'COPEL_ITEM_UNMAPPED' and i.severity == 'info' for i in parsed.issues))

    def test_unknown_energy_credit_labels_never_aggregate_or_classify(self):
        # Rótulos adversariais, não amostras reais nem suporte declarado a GD.
        rows = (*ITEMS, *[(label, 'kWh', str(i), '0,100000', '1,00', '', '', '')
                          for i, label in enumerate(('TESTE INJECAO GD-I', 'TESTE COMPENSACAO GD-II', 'TESTE SALDO CREDITO'), 1)])
        parsed = self.parse(items=rows)
        self.assertEqual([r['quantidade'].value for r in parsed.itens[-3:]], [Decimal('1'), Decimal('2'), Decimal('3')])
        self.assertTrue(all(v.value is None for k, v in parsed.energia.items() if k != 'consumo_kwh'))
        self.assertTrue(all(r['category'].value == 'unclassified' for r in parsed.energy_components[-3:]))
        self.assertTrue(all(r['descricao_normalizada'].status == 'not_present' for r in parsed.itens[-3:]))

    def test_bad_tariff_fails_without_discarding_original(self):
        row = list(ITEMS[1])
        row[3] = 'ILEGIVEL'
        parsed = self.parse(items=(ITEMS[0], tuple(row), *ITEMS[2:]))
        self.assertEqual(parsed.itens[1]['preco_unitario_com_tributos'].status, 'failed')
        self.assertEqual(parsed.itens[1]['descricao_original'].value, ITEMS[1][0])

    def test_notices_do_not_assert_auto_debit_is_active(self):
        parsed = self.parse()
        self.assertEqual(len(parsed.avisos), 4)
        self.assertTrue(any('PARA CADASTRO' in a.value for a in parsed.avisos))
        self.assertNotIn('debito_automatico', parsed.energia)

    def test_shifted_deep_layout_and_no_network(self):
        with patch('socket.socket.connect', side_effect=AssertionError('No network')) as connect:
            original, shifted = self.parse(), self.parse(shift=(3, -4))
        self.assertEqual(original.itens, shifted.itens)
        self.assertEqual(original.tributos, shifted.tributos)
        self.assertEqual(original.historico_consumo, shifted.historico_consumo)
        connect.assert_not_called()


if __name__ == '__main__':
    unittest.main()
