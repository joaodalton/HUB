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
from models.user import User
from utils.auth import generate_token
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
            users = [
                User(empresa_id=1, nome=role.title(), email=f'fatura-{role}@example.test', password_hash='x', role=role)
                for role in ('owner', 'admin', 'financial', 'operator', 'viewer')
            ]
            db.session.add_all([fatura_a, fatura_b, *users])
            db.session.commit()
            cls.fatura_a, cls.fatura_b = fatura_a.id, fatura_b.id
            cls.user_ids = {user.role: user.id for user in users}

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

    def test_legacy_rows_remain_readable_without_invented_workflow(self):
        response = self._request('owner', f'/api/v1/faturas/{self.fatura_a}')
        self.assertEqual(response.status_code, 200)
        row = response.json['data']
        self.assertEqual(row['asaasId'], 'pay_same')
        self.assertEqual(row['valor'], 10)
        for field in ('statusInterno', 'externalReference', 'paymentProvider'):
            self.assertIsNone(row[field])

    def _request(self, role: str, path: str, method: str = 'GET', body: dict | None = None):
        with self.app.app_context():
            token = generate_token(self.user_ids[role])
        return self.app.test_client().open(path, method=method, headers={'Authorization': f'Bearer {token}'}, json=body)

    def test_operator_and_viewer_are_read_only_for_faturas(self):
        for role in ('operator', 'viewer'):
            self.assertEqual(self._request(role, '/api/v1/faturas').status_code, 200)
            self.assertEqual(self._request(role, f'/api/v1/faturas/{self.fatura_a}').status_code, 200)
            self.assertEqual(self._request(role, '/api/v1/faturas', 'POST', {}).status_code, 403)
            self.assertEqual(self._request(role, f'/api/v1/faturas/{self.fatura_a}/sincronizar', 'POST').status_code, 403)
            self.assertEqual(self._request(role, f'/api/v1/faturas/{self.fatura_a}/cancelar', 'POST').status_code, 403)

    def test_financial_roles_keep_fatura_mutation_permission(self):
        for role in ('owner', 'admin', 'financial'):
            self.assertEqual(self._request(role, '/api/v1/faturas', 'POST', {}).status_code, 400)
            self.assertEqual(self._request(role, f'/api/v1/faturas/{self.fatura_a}/sincronizar', 'POST').status_code, 503)
            self.assertEqual(self._request(role, f'/api/v1/faturas/{self.fatura_a}/cancelar', 'POST').status_code, 503)


if __name__ == '__main__':
    unittest.main()
