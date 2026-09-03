"""Schema financeiro: tenant no espelho local da cobrança ASAAS."""
import os
import sys
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

_DB = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_DB.close()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flask import g
from app import create_app
from extensions import db
from models.client import Client
from models.consumer_unit import ConsumerUnit
from models.empresa import Empresa
from models.fatura import Fatura
try:
    from .support import IsolatedTestRuntime
except ImportError:
    from support import IsolatedTestRuntime


class FaturaModelTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepare_test_runtime(f"sqlite:///{_DB.name.replace(chr(92), '/')}", 'fatura-model-test')
        cls.app = create_app()
        with cls.app.app_context():
            db.create_all()
            db.session.add_all([Empresa(nome='A', slug='fatura-a'), Empresa(nome='B', slug='fatura-b')])
            db.session.flush()
            client_a = Client(empresa_id=1, nome='A', cpf='12345678900', email='a@example.test', asaas_customer_id='cus_a')
            client_b = Client(empresa_id=2, nome='B', cpf='12345678901', email='b@example.test', asaas_customer_id='cus_b')
            db.session.add_all([client_a, client_b])
            db.session.flush()
            uc_a = ConsumerUnit(empresa_id=1, client_id=client_a.id, codigo='UC-A')
            uc_b = ConsumerUnit(empresa_id=2, client_id=client_b.id, codigo='UC-B')
            db.session.add_all([uc_a, uc_b])
            db.session.flush()
            fatura_a = Fatura(empresa_id=1, client_id=client_a.id, consumer_unit_id=uc_a.id, concessionaria='Copel', competencia='2026-09', valor=Decimal('10.00'), mes_vencimento=date(2026, 9, 10), asaas_id='pay_same')
            fatura_b = Fatura(empresa_id=2, client_id=client_b.id, consumer_unit_id=uc_b.id, concessionaria='Copel', competencia='2026-09', valor=Decimal('20.00'), mes_vencimento=date(2026, 9, 10), asaas_id='pay_same')
            db.session.add_all([fatura_a, fatura_b])
            db.session.commit()
            cls.fatura_a, cls.fatura_b = fatura_a.id, fatura_b.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        os.unlink(_DB.name)
        cls.restore_test_runtime()

    def test_identity_map_never_crosses_fatura_tenants(self):
        with self.app.test_request_context('/'):
            g.current_empresa_id = 2
            self.assertIsNotNone(Fatura.query.filter_by(id=self.fatura_b).first())
            g.current_empresa_id = 1
            self.assertIsNone(Fatura.query.filter_by(id=self.fatura_b).first())
            self.assertEqual(Fatura.query.filter_by(id=self.fatura_a).first().asaas_id, 'pay_same')


if __name__ == '__main__':
    unittest.main()
