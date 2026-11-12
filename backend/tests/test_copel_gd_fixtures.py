"""Fixtures Copel ficticias com GD I, GD II e ambas."""
from decimal import Decimal
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.invoice_normalization_service import InvoiceNormalizer
from services.invoice_parsers.copel import CopelDANF3EParser
try:
    from .fixtures.invoices.copel.build_fixture import GD_CASES, make_gd_pdf
except ImportError:
    from fixtures.invoices.copel.build_fixture import GD_CASES, make_gd_pdf

DIR = Path(__file__).parent / 'fixtures' / 'invoices' / 'copel'
EXPECTED = {'gd1': {'GD_I': Decimal('120')}, 'gd2': {'GD_II': Decimal('210')},
            'gd1_gd2': {'GD_I': Decimal('30'), 'GD_II': Decimal('352')}}


def compensated(case):
    parsed = CopelDANF3EParser().parse(make_gd_pdf(case))
    return parsed, [c for c in parsed.energy_components if c['category'].value == 'compensated']


class CopelGdFixturesTest(unittest.TestCase):
    def test_each_case_extracts_only_its_gd_classes(self):
        for case, expected in EXPECTED.items():
            by_gd = {}
            for c in compensated(case)[1]:  # TE e TUSD da mesma identidade = uma quantidade fisica
                by_gd.setdefault((c['gd_classification'].value, c['credit_month'].value), set()).add(abs(c['amount_kwh'].value))
            totals = {}
            for (gd, _), amounts in by_gd.items():
                self.assertEqual(len(amounts), 1)
                totals[gd] = totals.get(gd, Decimal('0')) + amounts.pop()
            self.assertEqual(totals, expected)

    def test_tus_is_normalized_to_tusd(self):
        self.assertEqual({c['tariff_component'].value for c in compensated('gd2')[1]}, {'TE', 'TUSD'})

    def test_committed_pdfs_match_generator(self):
        for case in GD_CASES:
            self.assertEqual((DIR / f'{case}_anon.pdf').read_bytes(), make_gd_pdf(case))

    def test_expected_json_matches_normalizer(self):
        for case in GD_CASES:
            expected = json.loads((DIR / f'{case}_anon.expected.json').read_text(encoding='utf-8'))
            parsed, _ = compensated(case)
            campos = InvoiceNormalizer().normalize(parsed).campos
            self.assertEqual(campos['codigo_uc_documental'].value, expected['uc'])
            self.assertEqual(campos['mes_referencia'].value, expected['competencia'])
            self.assertEqual(campos['data_vencimento'].value.isoformat(), expected['vencimento'])
            self.assertEqual(campos['valor_total_concessionaria'].value, Decimal(expected['total']))
            got = [{'tariff_component': c['tariff_component'].value, 'gd_classification': c['gd_classification'].value,
                    'credit_month': c['credit_month'].value, 'amount_kwh': str(c['amount_kwh'].value)}
                   for c in compensated(case)[1]]
            self.assertEqual(got, expected['gd_components'])

    def test_cases_do_not_collide_on_upload_identity(self):
        pdfs = [make_gd_pdf(c) for c in GD_CASES]
        self.assertEqual(len(set(pdfs)), 3)
        keys = {GD_CASES[c]['changes'][k] for c in GD_CASES for k in ('uc', 'fiscal', 'key')}
        self.assertEqual(len(keys), 9)


if __name__ == '__main__':
    unittest.main()
