import hashlib
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flask import g
from app import create_app
from extensions import db
from models.client import Client
from models.consumer_unit import ConsumerUnit
from models.document import Document
from models.empresa import Empresa
from models.fatura_concessionaria import FaturaConcessionaria
from services.fatura_processing_service import FaturaProcessingService, ProcessingStatus
from services.invoice_parsers.registry import ParserRegistry
from services.invoice_parsers.schemas import ParsedInvoice
try:
    from .support import IsolatedTestRuntime
    from .test_invoice_parsers import FakeParser, OtherParser, sample_pdf
except ImportError:
    from support import IsolatedTestRuntime
    from test_invoice_parsers import FakeParser, OtherParser, sample_pdf


class FaturaProcessingTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepare_test_runtime('sqlite://', 'f3-processing-test')
        cls.app = create_app()
        cls.pdf = sample_pdf()
        with cls.app.app_context():
            db.create_all()
            for tenant in (1, 2):
                db.session.add(Empresa(id=tenant, nome='Teste', slug=f'f3-{tenant}'))
                db.session.add(Client(
                    id=tenant, empresa_id=tenant, nome='Teste', cpf=str(tenant),
                    email=f'f3-{tenant}@test.local',
                ))
                db.session.add(Document(
                    id=tenant, empresa_id=tenant, client_id=tenant, nome='test.pdf',
                    storage_provider='google_drive', storage_ref=f'test-{tenant}',
                ))
                db.session.add(FaturaConcessionaria(
                    id=tenant, empresa_id=tenant, client_id=tenant, document_id=tenant,
                    arquivo_hash=hashlib.sha256(cls.pdf).hexdigest(),
                ))
            db.session.commit()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        cls.restore_test_runtime()

    def setUp(self):
        self.context = self.app.test_request_context('/')
        self.context.push()
        self.addCleanup(self.context.pop)
        g.current_empresa_id = 1
        # Falha imediatamente se qualquer caminho tentar abrir conexão externa.
        self.network = patch('socket.socket.connect', side_effect=AssertionError('External I/O'))
        self.network_mock = self.network.start()
        self.addCleanup(self.network.stop)

    def test_empty_registry_without_external_api_or_persistence(self):
        invoice = FaturaConcessionaria.query.filter_by(id=1).one()
        before = invoice.to_dict()
        result = FaturaProcessingService().process(1, document=self.pdf, persist=False)
        self.assertEqual(result.status, ProcessingStatus.NOT_RECOGNIZED)
        self.assertIsNone(result.parsed)
        self.assertEqual(invoice.to_dict(), before)
        self.assertFalse(db.session.dirty)
        self.network_mock.assert_not_called()

    def test_fake_success_preserves_source_and_never_marks_extraida(self):
        service = FaturaProcessingService(ParserRegistry((FakeParser(),)))
        with patch.object(db.session, 'commit', side_effect=AssertionError('No commit')) as commit:
            result = service.process(1, document=self.pdf, persist=False)
        self.assertEqual(result.status, ProcessingStatus.PARSED)
        self.assertEqual(result.issues[0].code, 'TEST_INFO')
        invoice = FaturaConcessionaria.query.filter_by(id=1).one()
        self.assertEqual(invoice.status_extracao, 'recebida')
        self.assertIsNone(invoice.parser_name)
        self.assertIsNone(invoice.dados_brutos_extraidos)
        self.assertIsNone(invoice.valor_total_concessionaria)
        commit.assert_not_called()
        self.network_mock.assert_not_called()

    def test_tenants_missing_context_and_foreign_identity_map(self):
        g.current_empresa_id = 2
        foreign = FaturaConcessionaria.query.filter_by(id=2).one()
        g.current_empresa_id = 1
        service = FaturaProcessingService()
        for identifier in (foreign.id, 999):
            result = service.process(identifier, document=self.pdf, persist=False)
            self.assertEqual(result.issues[0].code, 'INVOICE_NOT_FOUND')
            self.assertIsNone(result.raw)
        g.current_empresa_id = 2
        self.assertEqual(service.process(2, document=self.pdf, persist=False).status, ProcessingStatus.NOT_RECOGNIZED)
        g.current_empresa_id = None
        self.assertEqual(service.process(1, document=self.pdf, persist=False).issues[0].code, 'TENANT_REQUIRED')
        self.network_mock.assert_not_called()

    def test_foreign_document_is_hidden(self):
        invoice = FaturaConcessionaria.query.filter_by(id=1).one()
        invoice.document_id = 2
        try:
            result = FaturaProcessingService().process(1, document=self.pdf, persist=False)
            self.assertEqual(result.issues[0].code, 'DOCUMENT_NOT_FOUND')
        finally:
            db.session.rollback()

    def test_changed_bytes_rejected_before_extraction(self):
        with patch('services.fatura_processing_service.MinimalExtractor.extract') as extract:
            result = FaturaProcessingService().process(1, document=self.pdf + b'changed', persist=False)
        self.assertEqual(result.issues[0].code, 'DOCUMENT_HASH_MISMATCH')
        extract.assert_not_called()

    def test_ambiguity_never_parses(self):
        service = FaturaProcessingService(ParserRegistry((FakeParser(), OtherParser())))
        with patch.object(FakeParser, 'parse') as parse:
            result = service.process(1, document=self.pdf, persist=False)
        self.assertEqual(result.status, ProcessingStatus.AMBIGUOUS)
        parse.assert_not_called()

    def test_technical_errors_are_structured_and_redacted(self):
        service = FaturaProcessingService(ParserRegistry((FakeParser(),)))
        targets = (
            'services.fatura_processing_service.MinimalExtractor.extract',
            f'{FakeParser.__module__}.FakeParser.can_parse',
            f'{FakeParser.__module__}.FakeParser.parse',
        )
        for target in targets:
            with self.subTest(target=target), patch(target, side_effect=RuntimeError('SECRET PDF CONTENT')):
                result = service.process(1, document=self.pdf, persist=False)
            self.assertEqual(result.status, ProcessingStatus.ERROR)
            self.assertEqual(result.issues[0].code, 'PARSING_EXECUTION_FAILED')
            self.assertNotIn('SECRET', repr(result))
        self.network_mock.assert_not_called()

    def test_wrong_parser_version_is_execution_error(self):
        service = FaturaProcessingService(ParserRegistry((FakeParser(),)))
        with patch.object(FakeParser, 'parse', return_value=ParsedInvoice(OtherParser.identity)):
            result = service.process(1, document=self.pdf, persist=False)
        self.assertEqual(result.status, ProcessingStatus.ERROR)

    def test_copel_default_registry_end_to_end_without_persistence(self):
        path = Path(__file__).parent / 'fixtures/invoices/copel/core_anon.pdf'
        document = path.read_bytes()
        invoice = FaturaConcessionaria.query.filter_by(id=1).one()
        invoice.arquivo_hash = hashlib.sha256(document).hexdigest()
        db.session.flush()
        before = invoice.to_dict()
        try:
            result = FaturaProcessingService().process(1, document=document, persist=False)
            self.assertEqual(result.status, ProcessingStatus.PARSED)
            self.assertEqual(result.parsed.identity.parser_name, 'copel')
            self.assertEqual(str(result.parsed.resumo['valor_total_concessionaria'].value), '1234.567890')
            self.assertEqual(invoice.to_dict(), before)
            self.assertFalse(db.session.dirty)
            self.network_mock.assert_not_called()
        finally:
            db.session.rollback()

    def test_deep_auto_debit_notice_does_not_update_uc(self):
        document = (Path(__file__).parent / 'fixtures/invoices/copel/core_anon.pdf').read_bytes()
        invoice = FaturaConcessionaria.query.filter_by(id=1).one()
        invoice.arquivo_hash = hashlib.sha256(document).hexdigest()
        uc = ConsumerUnit(empresa_id=1, client_id=1, codigo='UC-F5-FICTICIA')
        db.session.add(uc)
        db.session.flush()
        before = {column.name: getattr(uc, column.name) for column in ConsumerUnit.__table__.columns}
        try:
            result = FaturaProcessingService().process(1, document=document, persist=False)
            self.assertEqual(result.status, ProcessingStatus.PARSED)
            self.assertTrue(any('PARA CADASTRO' in a.value for a in result.parsed.avisos))
            self.assertEqual(before, {column.name: getattr(uc, column.name) for column in ConsumerUnit.__table__.columns})
            self.assertIsNone(invoice.consumer_unit_id)
            self.assertFalse(db.session.dirty)
            self.network_mock.assert_not_called()
        finally:
            db.session.rollback()


if __name__ == '__main__':
    unittest.main()
