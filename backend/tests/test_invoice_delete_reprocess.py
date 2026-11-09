"""Exclusao logica sem boleto e reprocessamento de fatura de concessionaria."""
import io
import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

_DB = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_DB.close()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from extensions import db
from models.calculo_cobranca import BillingCalculationExecution
from models.client import Client
from models.consumer_unit import ConsumerUnit
from models.document import Document
from models.empresa import Empresa
from models.fatura import Fatura
from models.fatura_concessionaria import FaturaConcessionaria
from models.pendencia import Pendencia
from models.user import User
from services import fatura_concessionaria_upload_service as upload_service
from services.fatura_processing_service import ProcessingStatus
from services.invoice_parsers.schemas import IssueSeverity
from utils.auth import generate_token
try:
    from .fixtures.invoices.copel.build_fixture import GD_CASES, make_gd_pdf, make_pdf
    from .support import IsolatedTestRuntime
    from .test_fatura_concessionaria_upload import FakeObjectStore
except ImportError:
    from fixtures.invoices.copel.build_fixture import GD_CASES, make_gd_pdf, make_pdf
    from support import IsolatedTestRuntime
    from test_fatura_concessionaria_upload import FakeObjectStore

BASE = '/api/v1/billing-calculations'
UC = '000000000000101'


class InvoiceDeleteReprocessTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepare_test_runtime(f"sqlite:///{_DB.name.replace(chr(92), '/')}", 'del-reprocess-test',
                                 limiter_enabled=False)
        cls.app = create_app()
        with cls.app.app_context():
            db.create_all()
            db.session.add_all([
                Empresa(id=1, nome='A', slug='dr-a'), Empresa(id=2, nome='B', slug='dr-b'),
                Client(id=1, empresa_id=1, nome='Cliente A', cpf='11111111111', email='a@t.local'),
                Client(id=2, empresa_id=2, nome='Cliente B', cpf='22222222222', email='b@t.local'),
                User(empresa_id=1, nome='o', email='owner@a.test', password_hash='x', role='owner'),
                User(empresa_id=2, nome='o', email='owner@b.test', password_hash='x', role='owner'),
            ])
            db.session.commit()
            cls.users = {u.email: u.id for u in User.query.all()}

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        os.unlink(_DB.name)
        cls.restore_test_runtime()

    def setUp(self):
        self.store = FakeObjectStore()
        self.patches = [patch.object(upload_service, 'get_object_storage', return_value=self.store),
                        patch('services.invoice_document_service.get_object_storage', return_value=self.store)]
        for p in self.patches:
            p.start()
        self.http = self.app.test_client()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        with self.app.app_context():
            # SQLite de teste nao tem os triggers de imutabilidade do PostgreSQL.
            db.session.execute(db.text('DELETE FROM billing_calculation_executions'))
            db.session.execute(db.text('DELETE FROM billing_calculation_snapshots'))
            for model in (Pendencia, Fatura, FaturaConcessionaria, Document, ConsumerUnit):
                model.query.delete()
            db.session.commit()

    def h(self, email='owner@a.test'):
        with self.app.app_context():
            return {'Authorization': f'Bearer {generate_token(self.users[email])}'}

    def add_uc(self, code=UC):
        with self.app.app_context():
            db.session.add(ConsumerUnit(empresa_id=1, client_id=1, codigo=code, concessionaria='Copel'))
            db.session.commit()

    def upload(self, pdf):
        return self.http.post('/api/v1/clients/1/invoices/upload', headers=self.h(),
            data={'arquivo': (io.BytesIO(pdf), 'f.pdf', 'application/pdf')}, content_type='multipart/form-data')

    def valid_invoice(self):
        self.add_uc()
        response = self.upload(make_gd_pdf('gd1'))
        self.assertEqual(response.status_code, 201, response.json)
        invoice_id = response.json['data']['invoiceId']
        with self.app.app_context():
            invoice = db.session.get(FaturaConcessionaria, invoice_id)
            self.assertEqual(invoice.status_validacao, 'valida')
            return invoice_id, invoice.consumer_unit_id, invoice.competencia

    def add_charge(self, uc_id, competencia, **kw):
        with self.app.app_context():
            db.session.add(Fatura(empresa_id=1, client_id=1, consumer_unit_id=uc_id, competencia=competencia,
                concessionaria='Copel', valor=10, mes_vencimento=date(2030, 10, 10), **kw))
            db.session.commit()

    def add_execution(self, invoice_id):
        with self.app.app_context():
            db.session.add(BillingCalculationExecution(empresa_id=1, fatura_concessionaria_id=invoice_id,
                status='MISSING_DATA', auditoria={'stages': []}))
            db.session.add(Pendencia(empresa_id=1, tipo='pendencia', categoria='Documentos', titulo='x',
                fatura_concessionaria_id=invoice_id))
            db.session.commit()

    def delete(self, invoice_id, email='owner@a.test'):
        return self.http.delete(f'{BASE}/invoices/{invoice_id}', headers=self.h(email))

    def reprocess(self, invoice_id, email='owner@a.test'):
        return self.http.post(f'{BASE}/invoices/{invoice_id}/reprocess', headers=self.h(email))

    def test_delete_with_calculation_is_soft_and_hides_invoice(self):
        invoice_id, _, _ = self.valid_invoice()
        self.add_execution(invoice_id)
        response = self.delete(invoice_id)
        self.assertEqual(response.status_code, 200, response.json)
        listing = self.http.get(f'{BASE}/invoices', headers=self.h()).json['data']
        self.assertNotIn(invoice_id, [row['id'] for row in listing])
        self.assertEqual(self.http.get(f'{BASE}/invoices/{invoice_id}/download', headers=self.h()).status_code, 404)
        self.assertEqual(self.delete(invoice_id).status_code, 404)
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(FaturaConcessionaria, invoice_id).deleted_at)
            self.assertEqual(BillingCalculationExecution.query.filter_by(
                fatura_concessionaria_id=invoice_id).count(), 1)
            self.assertEqual(Pendencia.query.filter_by(fatura_concessionaria_id=invoice_id).count(), 0)

    def test_delete_blocked_by_active_boleto_allowed_when_canceled(self):
        invoice_id, uc_id, comp = self.valid_invoice()
        self.add_charge(uc_id, comp, asaas_id='pay_1', asaas_status='pending')
        response = self.delete(invoice_id)
        self.assertEqual((response.status_code, response.json['code']), (409, 'INVOICE_HAS_BOLETO'))
        with self.app.app_context():
            Fatura.query.update({'asaas_status': 'canceled'})
            db.session.commit()
        self.assertEqual(self.delete(invoice_id).status_code, 200)

    def test_delete_blocked_by_pending_emission(self):
        invoice_id, uc_id, comp = self.valid_invoice()
        self.add_charge(uc_id, comp, asaas_id=None, status_interno='erro_emissao')
        response = self.delete(invoice_id)
        self.assertEqual((response.status_code, response.json['code']), (409, 'INVOICE_HAS_BOLETO'))
        with self.app.app_context():
            self.assertIsNone(db.session.get(FaturaConcessionaria, invoice_id).deleted_at)

    def test_other_tenant_gets_404_and_nothing_changes(self):
        invoice_id, _, _ = self.valid_invoice()
        self.assertEqual(self.delete(invoice_id, 'owner@b.test').status_code, 404)
        self.assertEqual(self.reprocess(invoice_id, 'owner@b.test').status_code, 404)
        with self.app.app_context():
            self.assertIsNone(db.session.get(FaturaConcessionaria, invoice_id).deleted_at)

    def test_reupload_after_delete_restores_same_invoice(self):
        invoice_id, _, _ = self.valid_invoice()
        self.assertEqual(self.delete(invoice_id).status_code, 200)
        response = self.upload(make_gd_pdf('gd1'))
        self.assertEqual(response.status_code, 201, response.json)
        self.assertFalse(response.json['data']['duplicate'])
        self.assertEqual(response.json['data']['invoiceId'], invoice_id)
        with self.app.app_context():
            invoice = db.session.get(FaturaConcessionaria, invoice_id)
            self.assertIsNone(invoice.deleted_at)
            self.assertEqual(invoice.status_validacao, 'valida')

    def test_deleted_invoice_does_not_cause_fiscal_key_conflict(self):
        invoice_id, _, _ = self.valid_invoice()
        self.assertEqual(self.delete(invoice_id).status_code, 200)
        case = GD_CASES['gd1']
        other = make_pdf(**{**case, 'changes': {**case['changes'], 'total': 'R$151,10'}})
        response = self.upload(other)
        self.assertEqual(response.status_code, 201, response.json)
        with self.app.app_context():
            new = FaturaConcessionaria.query.filter(FaturaConcessionaria.id != invoice_id).one()
            self.assertEqual(new.status_validacao, 'valida')

    def test_reprocess_uc_not_found_after_registering_uc_closes_error_pendencia(self):
        invoice_id = self.upload(make_gd_pdf('gd1')).json['data']['invoiceId']
        with self.app.app_context():
            self.assertEqual(db.session.get(FaturaConcessionaria, invoice_id).status_validacao,
                             'uc_nao_encontrada')
            db.session.add(Pendencia(empresa_id=1, tipo='erro', categoria='Documentos',
                origem=upload_service.ORIGEM_ERRO_PROCESSAMENTO, titulo='erro',
                fatura_concessionaria_id=invoice_id))
            db.session.commit()
        self.add_uc()
        result = self.reprocess(invoice_id)
        self.assertEqual(result.status_code, 200, result.json)
        with self.app.app_context():
            self.assertEqual(db.session.get(FaturaConcessionaria, invoice_id).status_validacao, 'valida')
            self.assertEqual(Pendencia.query.filter_by(fatura_concessionaria_id=invoice_id,
                origem=upload_service.ORIGEM_ERRO_PROCESSAMENTO).one().status, 'resolvida')

    def test_reprocess_revisao_necessaria(self):
        self.add_uc()
        invoice_id = self.upload(make_pdf(omitted=('total',), changes={'uc': UC})).json['data']['invoiceId']
        with self.app.app_context():
            self.assertEqual(db.session.get(FaturaConcessionaria, invoice_id).status_validacao,
                             'revisao_necessaria')
        result = self.reprocess(invoice_id)
        self.assertEqual(result.status_code, 200, result.json)

    def test_reprocess_refused_when_valid_or_boleto(self):
        invoice_id, uc_id, comp = self.valid_invoice()
        response = self.reprocess(invoice_id)
        self.assertEqual((response.status_code, response.json['code']), (409, 'REPROCESS_NOT_ALLOWED'))
        with self.app.app_context():
            db.session.get(FaturaConcessionaria, invoice_id).status_validacao = 'revisao_necessaria'
            db.session.commit()
        self.add_charge(uc_id, comp, asaas_id='pay_2', asaas_status='pending')
        response = self.reprocess(invoice_id)
        self.assertEqual((response.status_code, response.json['code']), (409, 'REPROCESS_NOT_ALLOWED'))

    def test_reprocess_of_other_tenants_invoice_is_404_and_untouched(self):
        invoice_id = self.upload(make_gd_pdf('gd1')).json['data']['invoiceId']
        self.assertEqual(self.reprocess(invoice_id, 'owner@b.test').status_code, 404)
        with self.app.app_context():
            self.assertEqual(db.session.get(FaturaConcessionaria, invoice_id).status_validacao,
                             'uc_nao_encontrada')

    def test_reprocess_refused_by_pending_emission(self):
        invoice_id = self.upload(make_gd_pdf('gd1')).json['data']['invoiceId']
        self.add_uc()
        with self.app.app_context():
            uc_id = ConsumerUnit.query.one().id
            invoice = db.session.get(FaturaConcessionaria, invoice_id)
            invoice.consumer_unit_id, invoice.competencia = uc_id, '2030-09'
            db.session.commit()
        self.add_charge(uc_id, '2030-09', asaas_id=None, status_interno='aguardando_emissao')
        response = self.reprocess(invoice_id)
        self.assertEqual((response.status_code, response.json['code']), (409, 'REPROCESS_NOT_ALLOWED'))

    def test_restore_with_active_boleto_skips_reprocess(self):
        invoice_id, uc_id, comp = self.valid_invoice()
        self.assertEqual(self.delete(invoice_id).status_code, 200)
        self.add_charge(uc_id, comp, asaas_id='pay_3', asaas_status='pending')
        with patch.object(upload_service.FaturaProcessingService, 'process') as process:
            response = self.upload(make_gd_pdf('gd1'))
        process.assert_not_called()
        self.assertEqual(response.status_code, 201, response.json)
        self.assertFalse(response.json['data']['duplicate'])
        with self.app.app_context():
            invoice = db.session.get(FaturaConcessionaria, invoice_id)
            self.assertIsNone(invoice.deleted_at)
            self.assertEqual(invoice.status_validacao, 'valida')

    def test_reprocess_critical_issue_creates_then_reopens_error_pendencia(self):
        invoice_id = self.upload(make_gd_pdf('gd1')).json['data']['invoiceId']
        critical = SimpleNamespace(status=ProcessingStatus.ERROR,
                                   issues=[SimpleNamespace(severity=IssueSeverity.CRITICAL, message='falha x')])
        origin = upload_service.ORIGEM_ERRO_PROCESSAMENTO
        with patch.object(upload_service.FaturaProcessingService, 'process', return_value=critical):
            self.assertEqual(self.reprocess(invoice_id).status_code, 200)
            with self.app.app_context():
                pend = Pendencia.query.filter_by(fatura_concessionaria_id=invoice_id, origem=origin).one()
                self.assertEqual(pend.status, 'aberta')
                pend.status = 'resolvida'
                db.session.commit()
            self.assertEqual(self.reprocess(invoice_id).status_code, 200)
        with self.app.app_context():
            pend = Pendencia.query.filter_by(fatura_concessionaria_id=invoice_id, origem=origin).one()
            self.assertEqual((pend.status, pend.resolved_at), ('aberta', None))

    def test_process_failure_does_not_500_and_leaves_invoice_reprocessable(self):
        invoice_id = self.upload(make_gd_pdf('gd1')).json['data']['invoiceId']
        self.add_uc()
        boom = patch.object(upload_service.FaturaProcessingService, 'process', side_effect=RuntimeError('x'))
        with boom:
            self.assertEqual(self.reprocess(invoice_id).status_code, 200)
        with self.app.app_context():
            self.assertEqual(db.session.get(FaturaConcessionaria, invoice_id).status_extracao, 'recebida')
        self.assertEqual(self.reprocess(invoice_id).status_code, 200)
        with self.app.app_context():
            self.assertEqual(db.session.get(FaturaConcessionaria, invoice_id).status_validacao, 'valida')
        self.assertEqual(self.delete(invoice_id).status_code, 200)
        with boom:
            response = self.upload(make_gd_pdf('gd1'))
        self.assertEqual(response.status_code, 201, response.json)
        with self.app.app_context():
            invoice = db.session.get(FaturaConcessionaria, invoice_id)
            self.assertEqual((invoice.deleted_at, invoice.status_extracao), (None, 'recebida'))
        self.assertEqual(self.reprocess(invoice_id).status_code, 200)
        with self.app.app_context():
            self.assertEqual(db.session.get(FaturaConcessionaria, invoice_id).status_validacao, 'valida')


if __name__ == '__main__':
    unittest.main()
