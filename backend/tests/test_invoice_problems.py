import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flask import g

from app import create_app
from extensions import db
from models.client import Client
from models.document import Document
from models.empresa import Empresa
from models.fatura_concessionaria import FaturaConcessionaria
from services.fatura_processing_service import FaturaProcessingService
from services.invoice_problems import gd_totals, invoice_problems
try:
    from .fixtures.invoices.copel.build_fixture import make_gd_pdf
    from .support import IsolatedTestRuntime
except ImportError:
    from fixtures.invoices.copel.build_fixture import make_gd_pdf
    from support import IsolatedTestRuntime


def _invoice(**kwargs):
    return FaturaConcessionaria(**kwargs)


class InvoiceProblemsTest(unittest.TestCase):
    def test_extraction_statuses(self):
        cases = {
            'recebida': ('NOT_PROCESSED', 'Fatura ainda não processada.'),
            'erro': ('EXTRACTION_FAILED', 'Não foi possível ler o PDF.'),
            'layout_nao_reconhecido': (
                'LAYOUT_NOT_RECOGNIZED', 'Layout de fatura não reconhecido (suportado: Copel DANF3E V1.06).'),
        }
        for status, (code, message) in cases.items():
            self.assertEqual(invoice_problems(_invoice(status_extracao=status)),
                             [{'code': code, 'message': message, 'fields': []}])

    def test_validation_statuses(self):
        extracted = dict(status_extracao='extraida', codigo_uc_extraido='000000000000101')
        self.assertEqual(invoice_problems(_invoice(status_validacao='uc_nao_encontrada', **extracted)), [
            {'code': 'UC_NOT_FOUND', 'message': 'UC 000000000000101 não está cadastrada em nenhum cliente.',
             'fields': []}])
        self.assertEqual(invoice_problems(_invoice(status_validacao='uc_pertence_outro_cliente', **extracted)), [
            {'code': 'UC_OTHER_CLIENT', 'message': 'UC 000000000000101 pertence a outro cliente.', 'fields': []}])
        self.assertEqual(invoice_problems(_invoice(status_validacao='valida', **extracted)), [])

    def test_review_required_lists_critical_fields(self):
        issues = [
            {'code': 'A', 'severity': 'critical', 'message': 'a', 'field': 'competencia'},
            {'code': 'B', 'severity': 'warning', 'message': 'b', 'field': 'multa'},
            {'code': 'C', 'severity': 'critical', 'message': 'c', 'field': 'valor_total_concessionaria'},
            {'code': 'D', 'severity': 'critical', 'message': 'd', 'field': 'competencia'},
        ]
        invoice = _invoice(status_extracao='extraida', status_validacao='revisao_necessaria',
                           dados_normalizados={'validation': {'issues': issues}})
        self.assertEqual(invoice_problems(invoice), [{
            'code': 'MISSING_FIELDS', 'message': 'Faltou ler: competencia, valor_total_concessionaria.',
            'fields': ['competencia', 'valor_total_concessionaria']}])

    def test_review_required_without_fields(self):
        issues = [{'code': 'A', 'severity': 'critical', 'message': 'um', 'field': None},
                  {'code': 'B', 'severity': 'critical', 'message': 'dois'}]
        invoice = _invoice(status_extracao='extraida', status_validacao='revisao_necessaria',
                           dados_normalizados={'validation': {'issues': issues}})
        self.assertEqual(invoice_problems(invoice),
                         [{'code': 'REVIEW_REQUIRED', 'message': 'um; dois', 'fields': []}])

    def test_gd_totals_without_extraction(self):
        self.assertEqual(gd_totals(_invoice()), {'gdIKwh': None, 'gdIIKwh': None})


class GdTotalsTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.prepare_test_runtime('sqlite:///' + (Path(cls.temp.name) / 'gd.db').as_posix(),
                                 'invoice-problems-test', limiter_enabled=False)
        cls.app = create_app()

    @classmethod
    def tearDownClass(cls):
        cls.restore_test_runtime()
        cls.temp.cleanup()

    def setUp(self):
        self.ctx = self.app.app_context()
        self.ctx.push()
        g.current_empresa_id = 10
        db.create_all()
        db.session.add(Empresa(id=10, nome='E', slug='gd-10'))
        db.session.add(Client(id=10, empresa_id=10, nome='C', cpf='10', email='c@example.test'))
        db.session.add(Document(id=10, empresa_id=10, client_id=10, nome='x.pdf', storage_provider='google_drive'))
        db.session.commit()

    def tearDown(self):
        db.session.rollback()
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.ctx.pop()

    def _processed(self, case):
        pdf = make_gd_pdf(case)
        invoice = FaturaConcessionaria(id=10, empresa_id=10, client_id=10, document_id=10,
                                       arquivo_hash=hashlib.sha256(pdf).hexdigest())
        db.session.add(invoice)
        db.session.commit()
        FaturaProcessingService().process(invoice.id, document=pdf)
        return db.session.get(FaturaConcessionaria, 10)

    def test_gd_totals_per_case(self):
        for case, expected in (('gd1_gd2', {'gdIKwh': '30', 'gdIIKwh': '352'}),
                               ('gd1', {'gdIKwh': '120', 'gdIIKwh': None}),
                               ('gd2', {'gdIKwh': None, 'gdIIKwh': '210'})):
            with self.subTest(case=case):
                self.assertEqual(gd_totals(self._processed(case)), expected)
                db.session.delete(db.session.get(FaturaConcessionaria, 10))
                db.session.commit()


if __name__ == '__main__':
    unittest.main()
