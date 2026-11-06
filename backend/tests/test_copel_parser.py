import ast
from datetime import date
from decimal import Decimal
from io import BytesIO
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from pypdf import PdfReader

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.invoice_parsers.copel import CopelDANF3EParser
from services.invoice_parsers.extraction import FullTextExtractor, MinimalExtractor
from services.invoice_parsers.registry import default_registry
from services.invoice_parsers.schemas import FieldStatus, RawExtraction
try:
    from .fixtures.invoices.copel.build_fixture import make_pdf
except ImportError:
    from fixtures.invoices.copel.build_fixture import make_pdf


FIXTURES = Path(__file__).parent / 'fixtures' / 'invoices' / 'copel'


class CopelParserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = (FIXTURES / 'core_anon.pdf').read_bytes()
        cls.parser = CopelDANF3EParser()

    def parse(self, **options):
        return self.parser.parse(make_pdf(**options))

    def test_real_layout_reconstruction_recognized(self):
        self.assertTrue(self.parser.can_parse(MinimalExtractor().extract(self.document)))

    def test_other_distributor_rejected(self):
        body = make_pdf(changes={'issuer': 'Outra Distribuidora', 'issuer_cnpj': 'CNPJ 00.000.000/0000-00'})
        self.assertFalse(self.parser.can_parse(MinimalExtractor().extract(body)))

    def test_word_copel_alone_rejected(self):
        self.assertFalse(self.parser.can_parse(RawExtraction('Copel', 1, (1,))))

    def test_each_recognition_anchor_is_required(self):
        for block in ('header', 'title', 'issuer', 'issuer_cnpj', 'footer'):
            with self.subTest(block=block):
                self.assertFalse(self.parser.can_parse(MinimalExtractor().extract(make_pdf(omitted=(block,)))))

    def test_unknown_version_rejected(self):
        self.assertFalse(self.parser.can_parse(MinimalExtractor().extract(
            make_pdf(changes={'footer': 'DANF3EA4B (V9.99)'}),
        )))

    def test_all_core_fields_match_expected(self):
        expected = json.loads((FIXTURES / 'core_anon.expected.json').read_text(encoding='utf-8'))
        parsed = self.parser.parse(self.document)
        for section, fields in expected.items():
            if section not in ('identificacao_fiscal', 'resumo', 'titular', 'leituras'):
                continue  # seções Deep têm sua própria regressão F5
            actual = parsed.leituras[0] if section == 'leituras' else getattr(parsed, section)
            for key, value in fields.items():
                with self.subTest(section=section, key=key):
                    self.assertEqual(actual[key].status, FieldStatus.FOUND)
                    self.assertEqual(str(actual[key].value), value)
                    self.assertIsInstance(actual[key].confidence, Decimal)
                    self.assertTrue(actual[key].source)

    def test_decimal_preserved_and_item_quantity_not_used(self):
        result = self.parser.parse(self.document).resumo
        for key, value in (('consumo_kwh', '225.123456'), ('valor_total_concessionaria', '1234.567890')):
            self.assertIsInstance(result[key].value, Decimal)
            self.assertEqual(str(result[key].value), value)
        self.assertNotEqual(result['consumo_kwh'].value, Decimal('999.99'))
        self.assertIsInstance(result['data_vencimento'].value, date)

    def test_absent_optional_field_is_not_present(self):
        field = self.parse(omitted=('cpf',)).titular['cpf_cnpj']
        self.assertEqual(field.status, FieldStatus.NOT_PRESENT)
        self.assertEqual(field.warnings[0].severity, 'warning')

    def test_absent_key_is_not_present_even_with_consult_label(self):
        field = self.parse(omitted=('key_label', 'key')).identificacao_fiscal['chave_acesso']
        self.assertEqual(field.status, FieldStatus.NOT_PRESENT)
        self.assertEqual(field.warnings[0].severity, 'critical')

    def test_masked_cpf_is_not_present_without_invented_digits(self):
        field = self.parser.parse(self.document).titular['cpf_cnpj']
        self.assertEqual(field.status, FieldStatus.NOT_PRESENT)
        self.assertIsNone(field.value)
        self.assertEqual(field.warnings[0].code, 'COPEL_CPF_MASKED')
        self.assertEqual(field.warnings[0].severity, 'info')

    def test_unreadable_cpf_remains_failed(self):
        field = self.parse(changes={'cpf': 'CPF: ILEGIVEL'}).titular['cpf_cnpj']
        self.assertEqual(field.status, FieldStatus.FAILED)
        self.assertIsNone(field.value)

    def test_readable_cpf_neutral_digits_transform(self):
        field = self.parse(changes={'cpf': 'CPF: 000.000.000-00'}).titular['cpf_cnpj']
        self.assertEqual(field.value, '00000000000')

    def test_illegible_total_failed(self):
        field = self.parse(changes={'total': 'R$ILEGIVEL'}).resumo['valor_total_concessionaria']
        self.assertEqual(field.status, FieldStatus.FAILED)
        self.assertIsNone(field.value)

    def test_invalid_dates_failed_without_financial_inference(self):
        field = self.parse(changes={'due': '31/02/2030'}).resumo['data_vencimento']
        self.assertEqual(field.status, FieldStatus.FAILED)

    def test_multiple_uc_candidates_ambiguous(self):
        field = self.parse(duplicate='000000000000002').identificacao_fiscal['codigo_uc']
        self.assertEqual(field.status, FieldStatus.AMBIGUOUS)
        self.assertIsNone(field.value)

    def test_multiple_competencias_ambiguous(self):
        field = self.parse(duplicate='09/2030   10/10/2030   R$100,00').identificacao_fiscal['competencia']
        self.assertEqual(field.status, FieldStatus.AMBIGUOUS)

    def test_identity_and_version(self):
        self.assertEqual(self.parser.parse(self.document).identity, self.parser.identity)
        self.assertEqual(self.parser.identity.parser_name, 'copel')
        self.assertEqual(self.parser.identity.layout_version, 'DANF3EA4B-V1.06')

    def test_shifted_layout_keeps_core(self):
        original = self.parser.parse(self.document)
        moved = self.parse(shift=(3, -4))
        self.assertEqual(original.identificacao_fiscal, moved.identificacao_fiscal)
        self.assertEqual(original.resumo, moved.resumo)
        self.assertEqual(original.titular, moved.titular)

    def test_registry_selects_copel(self):
        selected = default_registry().select(MinimalExtractor().extract(self.document))
        self.assertIsInstance(selected.parser, CopelDANF3EParser)

    def test_full_extraction_preserves_pages_and_minimal_contract(self):
        raw = FullTextExtractor().extract(self.document)
        self.assertEqual((raw.page_count, raw.extracted_pages), (2, (1, 2)))
        self.assertEqual(len(raw.page_texts), 2)
        self.assertEqual(MinimalExtractor().extract(self.document).page_texts, ())

    def test_no_network_no_financial_sections(self):
        with patch('socket.socket.connect', side_effect=AssertionError('No network')) as connect:
            parsed = self.parser.parse(self.document)
        connect.assert_not_called()
        self.assertEqual((len(parsed.itens), len(parsed.tributos), len(parsed.historico_consumo)), (4, 3, 13))
        self.assertIs(parsed.energia['consumo_kwh'], parsed.resumo['consumo_kwh'])
        self.assertTrue(all(v.value is None for k, v in parsed.energia.items() if k != 'consumo_kwh'))

    def test_processing_has_no_copel_knowledge(self):
        path = Path(__file__).resolve().parents[1] / 'services' / 'fatura_processing_service.py'
        self.assertNotIn('copel', path.read_text(encoding='utf-8').lower())
        tree = ast.parse(path.read_text(encoding='utf-8'))
        self.assertTrue(any(isinstance(node, ast.Name) and node.id == 'default_registry' for node in ast.walk(tree)))

    def test_fixture_has_no_original_images_or_active_links(self):
        reader = PdfReader(BytesIO(self.document))
        self.assertEqual(reader.metadata.author, 'HUB tests')
        for page in reader.pages:
            self.assertFalse(page.get('/Annots'))
            self.assertEqual(len(page.images), 0)


if __name__ == '__main__':
    unittest.main()
