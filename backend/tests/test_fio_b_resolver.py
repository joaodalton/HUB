"""C5.4: transição regulatória com tarifas explicitamente comprovadas."""
from dataclasses import replace
from decimal import Decimal, localcontext, ROUND_DOWN
import unittest
from unittest.mock import patch

from services.fio_b_resolver import FioBResolver, RegulatoryFioBTariff
from tests.test_document_tariff_resolver import compensation_invoice, found
from tests.test_commercial_tariff_selector import EVENTS


def invoice(gd='GD_II', month='2026-09', tariff='0.20'):
    result = compensation_invoice(({**EVENTS[1], 'gd': gd, 'quantity': '-1000'},))
    if tariff is not None:
        result.itens_documentais[1]['tusd_fio_b_unit_tariff'] = found(Decimal(tariff))
        # Normalização copia a evidência do item para a compensação.
        result.billing_energy_input.compensacoes[0].componentes[1].documento['tusd_fio_b_unit_tariff'] = result.itens_documentais[1]['tusd_fio_b_unit_tariff']
    return replace(result, billing_energy_input=replace(result.billing_energy_input,
        competencia=month, fatura_concessionaria_id=3))


class FioBResolverTest(unittest.TestCase):
    def test_transition_uses_invoice_year_not_credit_month_or_clock(self):
        for year, rate, amount in ((2023, '.15', '30'), (2024, '.30', '60'),
                (2025, '.45', '90'), (2026, '.60', '120'), (2027, '.75', '150'), (2028, '.90', '180')):
            with self.subTest(year=year):
                result = FioBResolver().resolve(invoice(month=f'{year}-09'))[0]
                self.assertEqual(result.status, 'RESOLVED')
                self.assertEqual(result.transition_rate, Decimal(rate))
                self.assertEqual(result.amount, Decimal(amount))
                self.assertEqual(result.energy_kwh, Decimal('1000'))
                self.assertEqual(result.tariff_source, 'DOCUMENT')

    def test_gdi_not_applicable_and_gdiii_unsupported(self):
        for gd, expected in (('GD_I', 'NOT_APPLICABLE'), ('GD_III', 'UNSUPPORTED'), ('UNKNOWN', 'MISSING_DATA')):
            result = FioBResolver().resolve(invoice(gd=gd))[0]
            self.assertEqual(result.status, expected)
            self.assertIsNone(result.amount)

    def test_document_and_gdi_do_not_read_regulatory_dataset(self):
        with patch('services.regulatory_tariff_repository.RegulatoryTariffRepository.fio_b_tariffs',
                   side_effect=AssertionError('dataset indisponível')):
            self.assertEqual(FioBResolver().resolve(invoice(gd='GD_I', tariff=None))[0].status,
                             'NOT_APPLICABLE')
            self.assertEqual(FioBResolver().resolve(invoice())[0].tariff_source, 'DOCUMENT')

    def test_unimplemented_year_does_not_invent_rate(self):
        for month in ('2022-12', '2029-01', '2035-09'):
            result = FioBResolver().resolve(invoice(month=month))[0]
            self.assertEqual(result.status, 'UNSUPPORTED')
            self.assertIsNone(result.transition_rate)
            self.assertIsNone(result.amount)

    def test_total_tusd_is_not_fio_b(self):
        result = FioBResolver().resolve(invoice(tariff=None))[0]
        self.assertEqual(result.status, 'MISSING_DATA')
        self.assertIsNone(result.tusd_fio_b_unit_tariff)
        self.assertIsNone(result.amount)

    def test_formula_preserves_decimal_under_low_global_precision(self):
        with localcontext() as ctx:
            ctx.prec, ctx.rounding = 2, ROUND_DOWN
            result = FioBResolver().resolve(invoice(tariff='0.2000123456789'))[0]
        self.assertEqual(result.amount, Decimal('120.007407407340000'))

    def test_regulatory_exact_match_and_document_priority(self):
        record = RegulatoryFioBTariff('copel', '2026-01', '2026-12', 'B1', 'CONVENCIONAL',
            Decimal('.25'), 'synthetic:resolution-1', '1')
        data = invoice(tariff=None)
        data.campos.update({name: found(value) for name, value in (
            ('concessionaria', 'copel'), ('subgrupo_tarifario', 'B1'), ('modalidade_tarifaria', 'CONVENCIONAL'))})
        result = FioBResolver().resolve(data, regulatory_tariffs=(record,))[0]
        self.assertEqual((result.tariff_source, result.amount), ('REGULATORY', Decimal('150')))
        for bad in (replace(record, distributor='other'), replace(record, subgroup='B2'),
                    replace(record, valid_to='2026-08'), replace(record, tariff_class='RESIDENCIAL')):
            self.assertEqual(FioBResolver().resolve(data, regulatory_tariffs=(bad,))[0].status, 'MISSING_DATA')
        document = invoice()
        document.campos.update(data.campos)
        self.assertEqual(FioBResolver().resolve(document, regulatory_tariffs=(record,))[0].amount, Decimal('120'))
        self.assertEqual(FioBResolver().resolve(data, regulatory_tariffs=(record, record))[0].status, 'AMBIGUOUS')

    def test_local_aneel_copel_record_resolves_september_2026(self):
        data = invoice(month='2026-09', tariff=None)
        data.campos.update({name: found(value) for name, value in (
            ('concessionaria', 'Copel'), ('subgrupo_tarifario', 'B1'),
            ('modalidade_tarifaria', 'CONVENCIONAL'), ('classe_tarifaria', 'Residencial'),
            ('subclasse_tarifaria', 'Residencial'))})
        result = FioBResolver().resolve(data)[0]
        self.assertEqual((result.status, result.tariff_source), ('RESOLVED', 'REGULATORY'))
        self.assertEqual(result.tusd_fio_b_unit_tariff, Decimal('0.21453560037400001'))
        self.assertEqual(result.amount, Decimal('128.721360224400006000'))

    def test_local_aneel_record_does_not_apply_to_partial_vigency_months(self):
        for month in ('2026-06', '2027-06'):
            data = invoice(month=month, tariff=None)
            data.campos.update({name: found(value) for name, value in (
                ('concessionaria', 'Copel'), ('subgrupo_tarifario', 'B1'),
                ('modalidade_tarifaria', 'CONVENCIONAL'), ('classe_tarifaria', 'Residencial'),
                ('subclasse_tarifaria', 'Residencial'))})
            self.assertEqual(FioBResolver().resolve(data)[0].status, 'MISSING_DATA')

    def test_invalid_document_tariff_never_falls_back_to_total_tusd(self):
        for field in (found(Decimal('-1')), found('0.2')):
            data = invoice()
            data.itens_documentais[1]['tusd_fio_b_unit_tariff'] = field
            data.billing_energy_input.compensacoes[0].componentes[1].documento['tusd_fio_b_unit_tariff'] = field
            self.assertEqual(FioBResolver().resolve(data)[0].status, 'MISSING_DATA')

    def test_invalid_document_tariff_yields_to_matching_regulatory_record(self):
        data = invoice()
        field = found(Decimal('-1'))
        data.itens_documentais[1]['tusd_fio_b_unit_tariff'] = field
        data.billing_energy_input.compensacoes[0].componentes[1].documento['tusd_fio_b_unit_tariff'] = field
        data.campos.update({name: found(value) for name, value in (
            ('concessionaria', 'copel'), ('subgrupo_tarifario', 'B1'), ('modalidade_tarifaria', 'CONVENCIONAL'))})
        record = RegulatoryFioBTariff('copel', '2026-01', '2026-12', 'B1', 'CONVENCIONAL',
            Decimal('.25'), 'resolution:validated-1', '1')
        result = FioBResolver().resolve(data, regulatory_tariffs=(record,))[0]
        self.assertEqual((result.status, result.tariff_source, result.amount),
                         ('RESOLVED', 'REGULATORY', Decimal('150')))

    def test_regulatory_record_rejects_float(self):
        with self.assertRaises(ValueError):
            RegulatoryFioBTariff('copel', '2026-01', '2026-12', 'B1', 'CONVENCIONAL',
                .2, 'synthetic:resolution-1', '1')

    def test_documental_zero_is_distinct_from_absence(self):
        result = FioBResolver().resolve(invoice(tariff='0'))[0]
        self.assertEqual(result.status, 'RESOLVED')
        self.assertEqual(result.amount, Decimal('0'))

    def test_forged_document_field_without_matching_invoice_is_missing(self):
        data = invoice()
        data.billing_energy_input.compensacoes[0].componentes[1].documento['tusd_fio_b_unit_tariff'] = found(Decimal('999'))
        self.assertEqual(FioBResolver().resolve(data)[0].status, 'MISSING_DATA')

    def test_document_ambiguity_does_not_fall_back_to_regulatory_record(self):
        from services.invoice_parsers.schemas import ExtractedField
        data = invoice()
        field = ExtractedField('ambiguous', source='synthetic:document')
        data.itens_documentais[1]['tusd_fio_b_unit_tariff'] = field
        data.billing_energy_input.compensacoes[0].componentes[1].documento['tusd_fio_b_unit_tariff'] = field
        record = RegulatoryFioBTariff('copel', '2026-01', '2026-12', 'B1', 'CONVENCIONAL',
            Decimal('.25'), 'synthetic:resolution-1', '1')
        data.campos.update({name: found(value) for name, value in (
            ('concessionaria', 'copel'), ('subgrupo_tarifario', 'B1'), ('modalidade_tarifaria', 'CONVENCIONAL'))})
        self.assertEqual(FioBResolver().resolve(data, regulatory_tariffs=(record,))[0].status, 'AMBIGUOUS')

    def test_validated_copel_pdf_preserves_monthly_tax_fields(self):
        from services.commercial_deduction_resolver import document_tax_audit
        from tests.test_document_tariff_resolver import copel_invoice
        data = copel_invoice()
        audit = document_tax_audit(data)
        self.assertEqual((audit['pis']['base'], audit['pis']['rate'], audit['pis']['amount']),
                         (Decimal('80.02'), Decimal('1.1234'), Decimal('.90')))
        self.assertEqual((audit['cofins']['base'], audit['cofins']['rate'], audit['cofins']['amount']),
                         (Decimal('80.02'), Decimal('6.1234'), Decimal('4.90')))
        self.assertEqual(FioBResolver().resolve(data)[0].status, 'MISSING_DATA')
