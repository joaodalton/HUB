from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.invoice_parsers.copel import CopelDANF3EParser
from services.invoice_parsers.schemas import ExtractedField, ExtractionIssue
from services.invoice_normalization_service import InvoiceNormalizer, InvoiceNormalized, json_safe
from services.invoice_validation_service import InvoiceValidator, UCMatchCandidate


class InvoiceNormalizationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parsed = CopelDANF3EParser().parse((Path(__file__).parent / 'fixtures/invoices/copel/core_anon.pdf').read_bytes())

    def normalize(self, parsed=None):
        return InvoiceNormalizer().normalize(parsed or self.parsed, empresa_id=1, client_id=10)

    def validate(self, invoice=None, **options):
        options.setdefault('candidates', (UCMatchCandidate(20, 1, 10, '000000000000001'),))
        return InvoiceValidator().validate(invoice or self.normalize(), **options)

    def test_canonical_schema_context_identity_and_dates(self):
        normalized = self.normalize()
        self.assertIsInstance(normalized, InvoiceNormalized)
        self.assertEqual((normalized.empresa_id, normalized.client_id, normalized.consumer_unit_id), (1, 10, None))
        self.assertEqual(normalized.identity, self.parsed.identity)
        self.assertEqual(normalized.campos['mes_referencia'].value, '2030-08')
        self.assertEqual(normalized.campos['data_leitura'].value, date(2030, 8, 1))
        self.assertEqual(normalized.campos['data_vencimento'].value, date(2030, 9, 10))
        self.assertIsNone(normalized.campos['uc_numero'].value)

    def test_decimal_no_rounding_and_documented_zero(self):
        parsed = replace(self.parsed, resumo={**self.parsed.resumo, 'multa': ExtractedField('found', Decimal('0'))})
        normalized = self.normalize(parsed)
        self.assertEqual(normalized.campos['valor_total_concessionaria'].value, Decimal('1234.567890'))
        self.assertIsInstance(normalized.campos['valor_total_concessionaria'].value, Decimal)
        self.assertEqual(normalized.campos['multa'].value, Decimal('0'))
        self.assertIsNone(normalized.campos['juros'].value)

    def test_absence_failed_ambiguity_and_not_examined_distinct(self):
        for status in ('not_present', 'failed', 'ambiguous'):
            field = ExtractedField(status, 'candidate' if status == 'ambiguous' else None,
                                   warnings=(ExtractionIssue('TEST', 'warning', 'Uncertain'),))
            parsed = replace(self.parsed, resumo={**self.parsed.resumo, 'multa': field})
            actual = self.normalize(parsed).campos['multa']
            self.assertEqual(actual, field)
        self.assertEqual(self.normalize().campos['juros'].warnings[0].code, 'FIELD_NOT_EXAMINED')
        self.assertEqual(self.normalize().campos['gd1_kwh'].warnings[0].code, 'COPEL_ENERGY_NOT_SUPPORTED')

    def test_gd_never_inferred_as_injection(self):
        parsed = replace(self.parsed, energia={**self.parsed.energia, 'gd1_kwh': ExtractedField('found', Decimal('10'))})
        normalized = self.normalize(parsed)
        self.assertEqual(normalized.campos['gd1_kwh'].value, Decimal('10'))
        self.assertIsNone(normalized.campos['injecao_gdi_kwh'].value)
        for name in ('gd2_kwh', 'injecao_gdii_kwh', 'energia_compensada_kwh', 'saldo_credito_kwh'):
            self.assertIsNone(normalized.campos[name].value)

    def test_components_history_items_and_tariffs_preserved_without_selection(self):
        normalized = self.normalize()
        self.assertEqual(normalized.energy_components, self.parsed.energy_components)
        self.assertEqual(normalized.historico_consumo, self.parsed.historico_consumo)
        self.assertEqual(normalized.itens_documentais, self.parsed.itens)
        self.assertEqual(normalized.tributos, self.parsed.tributos)
        self.assertEqual(len(normalized.tariffs_documented), 4)
        self.assertEqual(normalized.tariffs_documented[0]['tarifa_unitaria'].value, Decimal('0.123456'))
        self.assertIsNone(normalized.campos['tarifa_base'].value)
        self.assertEqual(normalized.historico_consumo[0]['competencia'].value, 'AGO30')
        normalized.itens_documentais[0]['quantidade'] = ExtractedField('found', Decimal('9999'))
        self.assertNotEqual(normalized.itens_documentais, self.parsed.itens)

    def test_address_and_iso_date_transformations(self):
        parsed = replace(self.parsed, titular={**self.parsed.titular,
            'cep': ExtractedField('found', '00000-000'), 'uf': ExtractedField('found', ' pr '),
            'cpf_cnpj': ExtractedField('found', '000.000.000-00')},
            resumo={**self.parsed.resumo, 'data_emissao': ExtractedField('found', '2030-08-02')})
        fields = self.normalize(parsed).campos
        self.assertEqual([fields[k].value for k in ('cep', 'uf', 'cpf_cnpj')], ['00000000', 'PR', '00000000000'])
        self.assertEqual(fields['data_emissao'].value, date(2030, 8, 2))

    def test_invalid_dates_types_and_repeated_readings_not_selected(self):
        parsed = replace(self.parsed, resumo={**self.parsed.resumo,
            'data_vencimento': ExtractedField('found', 'bad'), 'multa': ExtractedField('found', '2.50')},
            leituras=self.parsed.leituras * 2)
        fields = self.normalize(parsed).campos
        self.assertEqual(fields['data_vencimento'].status, 'failed')
        self.assertEqual(fields['multa'].status, 'failed')
        self.assertEqual(fields['data_leitura'].status, 'ambiguous')

    def test_numeric_uc_is_not_coerced_and_loses_no_leading_zero(self):
        parsed = replace(self.parsed, identificacao_fiscal={**self.parsed.identificacao_fiscal,
            'codigo_uc': ExtractedField('found', 1)})
        self.assertEqual(self.normalize(parsed).campos['codigo_uc_documental'].status, 'failed')
        self.assertEqual(self.normalize().campos['codigo_uc_documental'].value, '000000000000001')

    def test_serializer_nested_exact_json_and_rejects_float(self):
        encoded = json.loads(json.dumps(json_safe(self.normalize()), allow_nan=False))
        self.assertEqual(encoded['campos']['valor_total_concessionaria']['value'], '1234.567890')
        self.assertEqual(encoded['campos']['data_vencimento']['value'], '2030-09-10')
        self.assertEqual(json_safe(datetime(2030, 1, 1)), '2030-01-01T00:00:00')
        for value in (1.5, Decimal('NaN'), {1: 'bad'}):
            with self.assertRaises((TypeError, ValueError)):
                json_safe(value)

    def test_validator_accepts_core_despite_optional_unsupported_gd_and_masked_cpf(self):
        result = self.validate()
        self.assertEqual(result.status, 'valida')
        self.assertEqual(result.consumer_unit_id, 20)
        self.assertEqual(result.critical_errors, ())

    def test_each_required_missing_is_review(self):
        for name in InvoiceValidator.REQUIRED:
            invoice = self.normalize()
            invoice.campos[name] = ExtractedField('not_present')
            with self.subTest(name=name):
                result = self.validate(invoice)
                self.assertEqual(result.status, 'revisao_necessaria')
                self.assertTrue(result.critical_errors)

    def test_missing_optional_fields_do_not_invalidate(self):
        parsed = replace(self.parsed, titular={}, historico_consumo=(), tributos=(), itens=(), energia={}, issues=())
        self.assertEqual(self.validate(self.normalize(parsed)).status, 'valida')

    def test_matching_statuses_context_and_ambiguity(self):
        for candidates, status in (((), 'uc_nao_encontrada'),
                ((UCMatchCandidate(2, 1, 11, 'X'),), 'uc_pertence_outro_cliente'),
                ((UCMatchCandidate(2, 2, 10, 'X'),), 'revisao_necessaria'),
                ((UCMatchCandidate(1, 1, 10, 'X'), UCMatchCandidate(2, 1, 10, 'X')), 'revisao_necessaria'),
                (None, 'revisao_necessaria')):
            result = self.validate(candidates=candidates)
            self.assertEqual(result.status, status)
            self.assertIsNone(result.consumer_unit_id)

    def test_fiscal_conflict_review_and_no_mutation(self):
        invoice = self.normalize()
        before = json_safe(invoice)
        result = self.validate(invoice, fiscal_conflict=True)
        self.assertEqual(result.status, 'revisao_necessaria')
        self.assertTrue(any(i.code == 'FISCAL_KEY_DIFFERENT_HASH' for i in result.issues))
        self.assertEqual(json_safe(invoice), before)

    def test_normalizer_validator_do_not_use_network_or_financial_services(self):
        with patch('socket.socket.connect', side_effect=AssertionError('Network')):
            self.assertEqual(self.validate().status, 'valida')
        for name in ('invoice_normalization_service.py', 'invoice_validation_service.py'):
            text = (Path(__file__).resolve().parents[1] / 'services' / name).read_text(encoding='utf-8')
            for forbidden in ('from models', 'import sqlalchemy', 'db.session', 'asaas_client', 'fatura_service'):
                self.assertNotIn(forbidden, text)


if __name__ == '__main__':
    unittest.main()
