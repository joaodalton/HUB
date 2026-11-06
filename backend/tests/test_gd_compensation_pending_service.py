import hashlib
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from threading import Barrier

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flask import g
from app import create_app
from extensions import db
from models.client import Client
from models.consumer_unit import ConsumerUnit, PlantConnection
from models.document import Document
from models.empresa import Empresa
from models.fatura_concessionaria import FaturaConcessionaria
from models.log_entry import LogEntry
from models.pendencia import Pendencia
from models.plant import Plant
from models.user import User
from services.fatura_processing_service import FaturaProcessingService
from services.gd_compensation_pending_service import ORIGIN, register
from services.invoice_validation_service import InvoiceValidationResult
from utils.auth import generate_token
try:
    from .fixtures.invoices.copel.build_fixture import make_pdf
    from .support import IsolatedTestRuntime
except ImportError:
    from fixtures.invoices.copel.build_fixture import make_pdf
    from support import IsolatedTestRuntime


class GdCompensationPendingServiceTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.prepare_test_runtime('sqlite:///' + (Path(cls.temp.name) / 'gd-pending.db').as_posix(), 'gd-pending-test')
        cls.app = create_app()
        with cls.app.app_context():
            db.create_all()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove(); db.drop_all(); db.engine.dispose()
        cls.restore_test_runtime()
        cls.temp.cleanup()

    def setUp(self):
        self.ctx = self.app.test_request_context('/'); self.ctx.push(); g.current_empresa_id = 1
        db.session.remove(); db.drop_all(); db.create_all()
        document = make_pdf()
        for tenant in (1, 2):
            db.session.add(Empresa(id=tenant, nome=f'E{tenant}', slug=f'gd-{tenant}'))
            db.session.add(Client(id=tenant, empresa_id=tenant, nome='C', cpf=str(tenant), email=f'{tenant}@x.test'))
            db.session.add(ConsumerUnit(id=tenant, empresa_id=tenant, client_id=tenant, codigo='000000000000001'))
            db.session.add(Document(id=tenant, empresa_id=tenant, client_id=tenant, nome='f.pdf', storage_provider='google_drive', storage_ref=str(tenant)))
            db.session.add(FaturaConcessionaria(id=tenant, empresa_id=tenant, client_id=tenant, consumer_unit_id=tenant,
                                                document_id=tenant, arquivo_hash=hashlib.sha256(document).hexdigest(), competencia='2030-08'))
            db.session.add(User(id=tenant, empresa_id=tenant, nome='U', email=f'u{tenant}@x.test',
                                password_hash='x', role='owner'))
        db.session.commit()
        result = FaturaProcessingService().process(1, document=document, persist=False)
        self.normalized = result.normalized
        self.validation = InvoiceValidationResult('valida', (), 1, '000000000000001')

    def tearDown(self):
        db.session.rollback(); self.ctx.pop()

    def plant(self, identifier, *, active=True, activation=date(2030, 1, 1), tenant=1):
        row = Plant(id=identifier, empresa_id=tenant, nome=f'P{identifier}', uc=str(identifier), kw_pico=1,
                    status='Ativa' if active else 'Implantacao', data_ativacao=activation)
        db.session.add(row); db.session.flush()
        db.session.add(PlantConnection(empresa_id=tenant, consumer_unit_id=tenant, plant_id=identifier, percentual=100))
        db.session.commit()
        return row

    def test_expected_compensation_creates_one_pending_and_one_internal_event(self):
        self.plant(10)
        first = register(1, self.normalized, self.validation)
        second = register(1, self.normalized, self.validation)
        self.assertEqual(first.id, second.id)
        self.assertEqual(Pendencia.query.filter_by(origem=ORIGIN).count(), 1)
        self.assertEqual(first.plant_id, 10)
        self.assertEqual((first.client_id, first.consumer_unit_id, first.document_id,
                          first.fatura_concessionaria_id), (1, 1, 1, 1))
        self.assertEqual(first.metadados['faturaId'], 1)
        self.assertEqual(first.metadados['plantIds'], [10])
        self.assertEqual(LogEntry.query.filter_by(acao='gd_compensation_unverified').count(), 1)

    def test_no_expectation_or_ambiguous_plants_do_not_assign_artificially(self):
        self.assertIsNone(register(1, self.normalized, self.validation))
        self.plant(10, active=False)
        self.assertIsNone(register(1, self.normalized, self.validation))
        db.session.query(PlantConnection).delete(); db.session.query(Plant).delete(); db.session.commit()
        self.plant(10, activation=date(2030, 9, 1))
        self.assertIsNone(register(1, self.normalized, self.validation))
        db.session.query(PlantConnection).delete(); db.session.query(Plant).delete(); db.session.commit()
        self.plant(10); self.plant(11)
        pending = register(1, self.normalized, self.validation)
        self.assertIsNone(pending.plant_id)
        self.assertEqual(pending.metadados['plantIds'], [10, 11])

    def test_foreign_tenant_and_unmatched_uc_do_not_create_pending(self):
        self.plant(20, tenant=2)
        self.assertIsNone(register(1, self.normalized, InvoiceValidationResult('valida', (), None, None)))
        self.assertEqual(Pendencia.query.count(), 0)

    def test_pending_is_hidden_from_other_tenant_list_and_detail(self):
        self.plant(10)
        pending = register(1, self.normalized, self.validation)
        client = self.app.test_client()
        own = {'Authorization': f'Bearer {generate_token(1)}'}
        other = {'Authorization': f'Bearer {generate_token(2)}'}
        self.assertEqual(client.get(f'/api/v1/pendencias/{pending.id}', headers=own).status_code, 200)
        self.assertEqual(client.get(f'/api/v1/pendencias/{pending.id}', headers=other).status_code, 404)
        self.assertEqual(client.get('/api/v1/pendencias', headers=other).json['data'], [])

    def test_concurrent_registration_keeps_one_pending(self):
        self.plant(10)
        gate = Barrier(2)

        def worker():
            with self.app.test_request_context('/'):
                g.current_empresa_id = 1
                gate.wait()
                try:
                    return register(1, self.normalized, self.validation).id
                finally:
                    db.session.remove()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: worker(), range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(Pendencia.query.filter_by(origem=ORIGIN).count(), 1)
