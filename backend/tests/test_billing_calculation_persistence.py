import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from flask import g
from sqlalchemy.exc import IntegrityError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from extensions import db
from models.client import Client
from models.document import Document
from models.empresa import Empresa
from models.fatura_concessionaria import FaturaConcessionaria

try:
    from .support import IsolatedTestRuntime
except ImportError:
    from support import IsolatedTestRuntime


class BillingCalculationPersistenceTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.prepare_test_runtime('sqlite:///' + (Path(cls.temp.name) / 'billing.db').as_posix(),
                                 'billing-persistence-test', limiter_enabled=False)
        cls.app = create_app()

    @classmethod
    def tearDownClass(cls):
        cls.restore_test_runtime()
        cls.temp.cleanup()

    def setUp(self):
        from models.calculo_cobranca import BillingCalculationExecution, BillingCalculationSnapshot
        self.Execution = BillingCalculationExecution
        self.Snapshot = BillingCalculationSnapshot
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        for tenant in (10, 20):
            db.session.add(Empresa(id=tenant, nome=f'Empresa {tenant}', slug=f'empresa-{tenant}'))
            db.session.add(Client(id=tenant, empresa_id=tenant, nome='Cliente', cpf=str(tenant),
                                  email=f'{tenant}@example.test'))
            db.session.add(Document(id=tenant, empresa_id=tenant, client_id=tenant,
                                    nome='fatura.pdf', storage_provider='google_drive'))
            db.session.add(FaturaConcessionaria(id=tenant, empresa_id=tenant, client_id=tenant,
                                                document_id=tenant, arquivo_hash=str(tenant) * 32))
        db.session.commit()

    def tearDown(self):
        db.session.rollback()
        db.session.remove()
        g.pop('current_empresa_id', None)
        db.engine.dispose()
        db.drop_all()
        db.engine.dispose()
        self.context.pop()

    def snapshot(self, tenant=10, fingerprint='a' * 64, amount=Decimal('13.42'), **changes):
        values = dict(empresa_id=tenant, fatura_concessionaria_id=tenant,
                      fingerprint=fingerprint, valor_final=amount,
                      regra_snapshot={'tarifa': Decimal('0.123456')},
                      entrada_normalizada={'energia': Decimal('10.000001')},
                      resultado={'hub_amount': Decimal('13.42')})
        return self.Snapshot(**{**values, **changes})

    def test_tenant_filter_hides_other_company_records(self):
        for tenant in (10, 20):
            snapshot = self.snapshot(tenant=tenant)
            db.session.add(snapshot)
            db.session.flush()
            db.session.add(self.Execution(empresa_id=tenant, fatura_concessionaria_id=tenant,
                                          snapshot_id=snapshot.id, status='CALCULATED',
                                          auditoria={'etapas': []}))
        db.session.commit()
        g.current_empresa_id = 10
        self.assertEqual([row.empresa_id for row in self.Snapshot.query.all()], [10])
        self.assertEqual([row.empresa_id for row in self.Execution.query.all()], [10])
        self.assertIsNone(self.Snapshot.query.filter_by(empresa_id=20).first())

    def test_json_payload_is_copied_and_decimal_is_text(self):
        source = {'tarifa': Decimal('0.123456'), 'nested': {'label': 'original'}}
        snapshot = self.snapshot(regra_snapshot=source)
        source['nested']['label'] = 'changed'
        db.session.add(snapshot)
        db.session.commit()
        db.session.expire_all()
        stored = self.Snapshot.query.one()
        self.assertEqual(stored.regra_snapshot, {'tarifa': '0.123456', 'nested': {'label': 'original'}})
        self.assertEqual(stored.entrada_normalizada['energia'], '10.000001')
        self.assertEqual(stored.resultado['hub_amount'], '13.42')

    def test_same_tenant_fingerprint_is_unique_but_other_tenant_can_reuse_it(self):
        db.session.add(self.snapshot())
        db.session.commit()
        db.session.add(self.snapshot())
        with self.assertRaises(IntegrityError):
            db.session.commit()
        db.session.rollback()
        db.session.add(self.snapshot(tenant=20))
        db.session.commit()
        self.assertEqual(self.Snapshot.query.count(), 2)

    def test_blocked_execution_has_no_snapshot_or_amount(self):
        db.session.add(self.Execution(empresa_id=10, fatura_concessionaria_id=10,
                                      status='MISSING_DATA', auditoria={'etapas': [{'status': 'MISSING_DATA'}]}))
        db.session.commit()
        execution = self.Execution.query.one()
        self.assertIsNone(execution.snapshot_id)
        self.assertFalse(hasattr(execution, 'valor_final'))
        db.session.add(self.Execution(empresa_id=10, fatura_concessionaria_id=10,
                                      status='CALCULATED', auditoria={}))
        with self.assertRaises(IntegrityError):
            db.session.commit()

    def test_material_input_change_can_create_new_fingerprint_snapshot(self):
        db.session.add_all([self.snapshot(fingerprint='a' * 64),
                            self.snapshot(fingerprint='b' * 64,
                                          entrada_normalizada={'energia': Decimal('11.000001')})])
        db.session.commit()
        self.assertEqual(self.Snapshot.query.count(), 2)

    def test_database_rejects_cross_tenant_invoice_and_snapshot_links(self):
        db.session.execute(db.text('PRAGMA foreign_keys=ON'))
        self.assertEqual(db.session.scalar(db.text('PRAGMA foreign_keys')), 1)
        db.session.add(self.snapshot(tenant=10, fatura_concessionaria_id=20))
        with self.assertRaises(IntegrityError):
            db.session.commit()
        db.session.rollback()

        db.session.add(self.Execution(empresa_id=10, fatura_concessionaria_id=20,
                                      status='MISSING_DATA', auditoria={}))
        with self.assertRaises(IntegrityError):
            db.session.commit()
        db.session.rollback()

        snapshot = self.snapshot(tenant=10)
        db.session.add(snapshot)
        db.session.commit()
        db.session.add(self.Execution(empresa_id=20, fatura_concessionaria_id=20,
                                      snapshot_id=snapshot.id, status='CALCULATED', auditoria={}))
        with self.assertRaises(IntegrityError):
            db.session.commit()

    def test_database_rejects_snapshot_from_other_invoice_in_same_tenant(self):
        db.session.execute(db.text('PRAGMA foreign_keys=ON'))
        db.session.add(FaturaConcessionaria(id=11, empresa_id=10, client_id=10,
                                            document_id=10, arquivo_hash='b' * 64))
        snapshot = self.snapshot(tenant=10)
        db.session.add(snapshot)
        db.session.commit()
        db.session.add(self.Execution(empresa_id=10, fatura_concessionaria_id=11,
                                      snapshot_id=snapshot.id, status='CALCULATED', auditoria={}))
        with self.assertRaises(IntegrityError):
            db.session.commit()

    def test_persisted_audit_rows_cannot_be_rewritten_or_deleted(self):
        snapshot = self.snapshot()
        db.session.add(snapshot)
        db.session.flush()
        execution = self.Execution(empresa_id=10, fatura_concessionaria_id=10,
                                   snapshot_id=snapshot.id, status='CALCULATED', auditoria={})
        db.session.add(execution)
        db.session.commit()
        snapshot.valor_final = Decimal('99.99')
        with self.assertRaises(ValueError):
            db.session.commit()
        db.session.rollback()
        execution.status = 'ERROR'
        with self.assertRaises(ValueError):
            db.session.commit()
        db.session.rollback()
        db.session.delete(snapshot)
        with self.assertRaises(ValueError):
            db.session.commit()


if __name__ == '__main__':
    unittest.main()
