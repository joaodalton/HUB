import ast
from dataclasses import asdict
from decimal import Decimal
from io import BytesIO
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen.canvas import Canvas

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.invoice_parsers.base import InvoiceParser
from services.invoice_parsers.extraction import MinimalExtractor
from services.invoice_parsers.registry import ParserRegistry
from services.invoice_parsers.schemas import (
    ExtractedField, ExtractionIssue, FieldStatus, IssueSeverity,
    ParsedInvoice, ParserIdentity, RawExtraction, RawTable, RawWord,
)


def sample_pdf():
    output = BytesIO()
    canvas = Canvas(output)
    for text in ('TEST LAYOUT', 'SECOND PAGE ONLY'):
        canvas.drawString(20, 700, text)
        canvas.showPage()
    canvas.save()
    return output.getvalue()


class FakeParser(InvoiceParser):
    identity = ParserIdentity('fake', '1.0.0', 'test', '1')

    def can_parse(self, raw):
        return 'TEST LAYOUT' in raw.text

    def parse(self, document):
        assert len(PdfReader(BytesIO(document)).pages) == 2
        return ParsedInvoice(
            identity=self.identity,
            resumo={'document_value': ExtractedField(
                FieldStatus.FOUND, Decimal('123.456789'),
                confidence=Decimal('0.99'), source='test label',
            )},
            issues=(ExtractionIssue('TEST_INFO', IssueSeverity.INFO, 'Teste.'),),
        )


class OtherParser(FakeParser):
    identity = ParserIdentity('other', '2.0.0')


class InvoiceParsersTest(unittest.TestCase):
    def test_found(self):
        field = ExtractedField('found', 'texto', Decimal('1'), 'anchor')
        self.assertEqual((field.status, field.value, field.source), (FieldStatus.FOUND, 'texto', 'anchor'))

    def test_not_present(self):
        self.assertIsNone(ExtractedField('not_present').value)
        with self.assertRaises(ValueError):
            ExtractedField('not_present', 'inventado')

    def test_failed(self):
        issue = ExtractionIssue('READ_FAILED', 'warning', 'Campo ilegível.', 'resumo.total')
        field = ExtractedField('failed', warnings=(issue,))
        self.assertEqual((field.status, field.warnings), (FieldStatus.FAILED, (issue,)))

    def test_ambiguous(self):
        issue = ExtractionIssue('TWO_VALUES', 'warning', 'Duas interpretações.', metadata={'candidates': 'A/B'})
        field = ExtractedField('ambiguous', 'A', warnings=(issue,))
        self.assertEqual(field.status, FieldStatus.AMBIGUOUS)
        self.assertEqual(field.warnings[0].metadata['candidates'], 'A/B')

    def test_issue_severities(self):
        for severity in ('info', 'warning', 'critical'):
            self.assertEqual(ExtractionIssue('CODE', severity, 'Mensagem.').severity.value, severity)
        with self.assertRaises(ValueError):
            ExtractionIssue('CODE', 'invalid', 'Mensagem.')

    def test_invalid_field_and_confidence_rejected(self):
        for status, value in (('unknown', None), ('found', None), ('failed', 'valor')):
            with self.subTest(status=status), self.assertRaises(ValueError):
                ExtractedField(status, value)
        for confidence in (Decimal('-0.1'), Decimal('1.1'), Decimal('NaN')):
            with self.assertRaises(ValueError):
                ExtractedField('found', 'x', confidence)
        with self.assertRaises(TypeError):
            ExtractedField('found', 'x', 0.99)

    def test_minimal_extractor_only_reads_first_page(self):
        from pypdf._page import PageObject
        original = PageObject.extract_text
        calls = []

        def track(page, *args, **kwargs):
            calls.append(page)
            return original(page, *args, **kwargs)

        with patch.object(PageObject, 'extract_text', track):
            raw = MinimalExtractor().extract(sample_pdf())
        self.assertEqual(len(calls), 1)
        self.assertEqual((raw.page_count, raw.extracted_pages), (2, (1,)))
        self.assertIn('TEST LAYOUT', raw.text)
        self.assertNotIn('SECOND PAGE ONLY', raw.text)
        self.assertIsNone(raw.words)
        self.assertIsNone(raw.tables)
        self.assertIn('/Producer', raw.metadata)

    def test_blank_page_has_technical_warning(self):
        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        output = BytesIO()
        writer.write(output)
        raw = MinimalExtractor().extract(output.getvalue())
        self.assertEqual(raw.text, '')
        self.assertEqual(raw.warnings[0].code, 'NO_TEXT_ON_FIRST_PAGE')

    def test_invalid_pdf_raises_execution_error(self):
        with self.assertRaises(Exception):
            MinimalExtractor().extract(b'invalid')

    def test_raw_supports_full_text_geometry_and_tables(self):
        word = RawWord('texto', 1, 1.0, 2.0, 3.0, 4.0)
        table = RawTable(1, (('label', '123,456789'),))
        raw = RawExtraction('full text', 1, (1,), words=(word,), tables=(table,))
        self.assertEqual(raw.words[0].text, 'texto')
        self.assertEqual(raw.tables[0].rows[0][1], '123,456789')

    def test_registry_selects_correct_parser(self):
        class RejectingParser(OtherParser):
            def can_parse(self, raw):
                return False

        parser = FakeParser()
        selection = ParserRegistry((RejectingParser(), parser)).select(
            MinimalExtractor().extract(sample_pdf()),
        )
        self.assertIs(selection.parser, parser)
        self.assertEqual(selection.issues, ())

    def test_registry_unknown(self):
        raw = RawExtraction('unknown', 1, (1,))
        for registry in (ParserRegistry(), ParserRegistry((FakeParser(),))):
            result = registry.select(raw)
            self.assertIsNone(result.parser)
            self.assertEqual(result.issues[0].code, 'LAYOUT_NOT_RECOGNIZED')

    def test_registry_ambiguity_does_not_choose_first(self):
        for parsers in ((FakeParser(), OtherParser()), (OtherParser(), FakeParser())):
            result = ParserRegistry(parsers).select(MinimalExtractor().extract(sample_pdf()))
            self.assertIsNone(result.parser)
            self.assertEqual(result.issues[0].code, 'AMBIGUOUS_LAYOUT')

    def test_registry_rejects_duplicate_and_invalid_claim(self):
        with self.assertRaises(ValueError):
            ParserRegistry((FakeParser(), FakeParser()))
        with patch.object(FakeParser, 'can_parse', return_value=0.9):
            with self.assertRaises(TypeError):
                ParserRegistry((FakeParser(),)).select(RawExtraction('', 1, (1,)))

    def test_fake_parsed_invoice_and_versioning(self):
        parsed = FakeParser().parse(sample_pdf())
        self.assertIsInstance(parsed, ParsedInvoice)
        self.assertEqual(asdict(parsed.identity), {
            'parser_name': 'fake', 'parser_version': '1.0.0',
            'layout_name': 'test', 'layout_version': '1',
        })
        with self.assertRaises(ValueError):
            ParserIdentity('', '1')
        with self.assertRaises(ValueError):
            ParserIdentity('test', '1', 'layout')
        with self.assertRaises(TypeError):
            ParsedInvoice(FakeParser.identity, resumo={'total': None})

    def test_decimal_preserved_without_float(self):
        parsed = FakeParser().parse(sample_pdf())
        value = asdict(parsed)['resumo']['document_value']['value']
        self.assertIsInstance(value, Decimal)
        self.assertEqual(str(value), '123.456789')
        with self.assertRaises(TypeError):
            ExtractedField('found', 123.456789)
        with self.assertRaises(ValueError):
            ExtractedField('found', Decimal('Infinity'))

    def test_parser_package_has_no_database_or_external_dependencies(self):
        folder = Path(__file__).resolve().parents[1] / 'services' / 'invoice_parsers'
        allowed = {'abc', 'dataclasses', 'datetime', 'decimal', 'enum', 'typing', 'io', 'pypdf', 're', 'unicodedata'}
        for path in folder.glob('*.py'):
            for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
                if isinstance(node, ast.Import):
                    for name in node.names:
                        self.assertIn(name.name.split('.')[0], allowed, str(path))
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    self.assertIn(node.module.split('.')[0], allowed, str(path))


if __name__ == '__main__':
    unittest.main()
