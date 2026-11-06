"""Contrato HTTP C5.5: RBAC, empresa explícita e histórico isolado."""
import sys
import tempfile
import unittest
from io import BytesIO
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from extensions import db
from models.calculo_cobranca import BillingCalculationExecution, BillingCalculationSnapshot
from models.client import Client
from models.consumer_unit import ConsumerUnit
from models.document import Document
from models.empresa import Empresa
from models.fatura import Fatura
from models.fatura_concessionaria import FaturaConcessionaria
from models.user import User
from utils.auth import generate_token

try:
    from .support import IsolatedTestRuntime
except ImportError:
    from support import IsolatedTestRuntime


class BillingCalculationRoutesTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.prepare_test_runtime('sqlite:///' + (Path(cls.temp.name) / 'routes.db').as_posix(),
                                 'billing-routes-test', limiter_enabled=False)
        cls.app = create_app()

    @classmethod
    def tearDownClass(cls):
        cls.restore_test_runtime()
        cls.temp.cleanup()

    def setUp(self):
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        for tenant in (10, 20):
            db.session.add(Empresa(id=tenant, nome=f'Empresa {tenant}', slug=f'calc-{tenant}'))
            db.session.add(Client(id=tenant, empresa_id=tenant, nome='Cliente', cpf=str(tenant),
                                  email=f'{tenant}@example.test'))
            db.session.add(Document(id=tenant, empresa_id=tenant, client_id=tenant,
                                    nome='copel.pdf', storage_provider='google_drive'))
            db.session.add(FaturaConcessionaria(id=tenant, empresa_id=tenant, client_id=tenant,
                                                document_id=tenant, arquivo_hash=str(tenant) * 32))
        users = ((1, 10, 'owner', False), (2, 10, 'financial', False),
                 (3, 10, 'operator', False), (4, 10, 'viewer', False),
                 (5, 20, 'owner', False), (6, 10, 'viewer', True))
        for user_id, tenant, role, platform in users:
            db.session.add(User(id=user_id, empresa_id=tenant, nome=role,
                                email=f'user-{user_id}@example.test', password_hash='x',
                                role=role, is_platform_admin=platform))
        db.session.commit()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.rollback()
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.ctx.pop()

    def headers(self, user_id):
        return {'Authorization': f'Bearer {generate_token(user_id)}'}

    def test_execute_requires_financial_permission_and_is_tenant_scoped(self):
        url = '/api/v1/billing-calculations/invoices/10/execute'
        self.assertEqual(self.client.post(url).status_code, 401)
        for user_id in (3, 4):
            self.assertEqual(self.client.post(url, headers=self.headers(user_id)).status_code, 403)
        self.assertEqual(self.client.post('/api/v1/billing-calculations/invoices/20/execute',
                                          headers=self.headers(1)).status_code, 404)
        response = self.client.post(url, headers=self.headers(2))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json['data']['status'], 'MISSING_DATA')
        self.assertIsNone(response.json['data']['snapshotId'])
        self.assertGreaterEqual(Decimal(response.json['data']['durationMs']), 0)

    def test_history_and_details_never_cross_tenant(self):
        snapshot = BillingCalculationSnapshot(empresa_id=20, fatura_concessionaria_id=20,
            fingerprint='b' * 64, regra_snapshot={}, entrada_normalizada={},
            resultado={'hub_amount': '7.42'}, valor_final=Decimal('7.42'))
        db.session.add(snapshot)
        db.session.flush()
        execution = BillingCalculationExecution(empresa_id=20, fatura_concessionaria_id=20,
            snapshot_id=snapshot.id, status='CALCULATED', auditoria={'stages': []})
        db.session.add(execution)
        db.session.commit()
        routes = ('', f'/executions/{execution.id}', f'/snapshots/{snapshot.id}')
        for route in routes:
            response = self.client.get('/api/v1/billing-calculations' + route,
                                       headers=self.headers(1))
            self.assertEqual(response.status_code, 200 if not route else 404)
            if not route:
                self.assertEqual(response.json['data'], [])
            self.assertEqual(self.client.get('/api/v1/billing-calculations' + route,
                                             headers=self.headers(4)).status_code, 403)
        response = self.client.get(f'/api/v1/billing-calculations/executions/{execution.id}',
                                   headers=self.headers(5))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['data']['snapshotId'], snapshot.id)

    def test_admin_diagnostic_requires_explicit_company_and_platform_flag(self):
        base = '/api/v1/platform/empresas/20/billing-calculations'
        for user_id in (1, 5):
            self.assertEqual(self.client.get(base, headers=self.headers(user_id)).status_code, 403)
        self.assertEqual(self.client.get('/api/v1/platform/billing-calculations',
                                         headers=self.headers(6)).status_code, 404)
        self.assertEqual(self.client.get('/api/v1/billing-calculations',
                                         headers=self.headers(6)).status_code, 403)
        self.assertEqual(self.client.get('/api/v1/platform/empresas/999/billing-calculations',
                                         headers=self.headers(6)).status_code, 404)
        self.assertEqual(self.client.get(base + '/invoices',
                                         headers=self.headers(6)).json['data'][0]['id'], 20)
        response = self.client.post(base + '/invoices/20/execute', headers=self.headers(6))
        self.assertEqual(response.status_code, 201)
        execution_id = response.json['data']['id']
        detail = self.client.get(base + f'/executions/{execution_id}', headers=self.headers(6))
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json['data']['empresaId'], 20)
        self.assertEqual(self.client.get('/api/v1/platform/empresas/10/billing-calculations'
                                         f'/executions/{execution_id}', headers=self.headers(6)).status_code, 404)

    def test_invoice_list_filters_before_pagination_and_preserves_tenant(self):
        first = db.session.get(FaturaConcessionaria, 10)
        first.competencia = '2026-09'
        first.valor_total_concessionaria = Decimal('123.45')
        first.status_validacao = 'valida'
        for identifier in (11, 12):
            db.session.add(FaturaConcessionaria(
                id=identifier, empresa_id=10, client_id=10, document_id=10,
                arquivo_hash=str(identifier) * 32, competencia='2026-08'))
        db.session.commit()
        base = '/api/v1/billing-calculations/invoices'
        response = self.client.get(base + '?competencia=2026-09&pageSize=1',
                                   headers=self.headers(1))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['pagination']['total'], 1)
        self.assertEqual(response.json['data'][0]['valorTotalConcessionaria'], '123.45')
        self.assertEqual(response.json['data'][0]['clienteNome'], 'Cliente')
        self.assertFalse(response.json['data'][0]['documentoDisponivel'])
        self.assertEqual(self.client.get(base + '?pageSize=1&page=2', headers=self.headers(1))
                         .json['pagination']['total'], 3)
        self.assertEqual(self.client.get(base, headers=self.headers(5)).json['pagination']['total'], 1)
        self.assertEqual(self.client.get(base + '?pageSize=101', headers=self.headers(1)).status_code, 400)

    def test_invoice_list_contains_only_contextual_charges_from_same_tenant(self):
        for tenant in (10, 20):
            db.session.add(ConsumerUnit(id=tenant, empresa_id=tenant, client_id=tenant,
                                        codigo=f'UC-{tenant}'))
            db.session.add(Fatura(empresa_id=tenant, client_id=tenant, consumer_unit_id=tenant,
                                  concessionaria='COPEL', competencia='2026-09',
                                  valor=Decimal('40.00'), mes_vencimento=date(2026, 10, 5),
                                  asaas_status='pending'))
            invoice = db.session.get(FaturaConcessionaria, tenant)
            invoice.consumer_unit_id = tenant
            invoice.competencia = '2026-09'
        db.session.commit()
        response = self.client.get('/api/v1/billing-calculations/invoices',
                                   headers=self.headers(1))
        self.assertEqual(response.status_code, 200)
        charges = response.json['data'][0]['contextualCharges']
        self.assertEqual(len(charges), 1)
        self.assertEqual(charges[0]['valor'], 40.0)
        self.assertEqual(response.json['data'][0]['ucCodigo'], 'UC-10')

    def test_platform_upload_reuses_existing_validation_and_tenant_client_check(self):
        base = '/api/v1/platform/empresas/20/billing-calculations/clients'
        url = base + '/10/invoices/upload'
        pdf = {'arquivo': (BytesIO(b'%PDF-invalid'), 'fatura.pdf', 'application/pdf')}
        self.assertEqual(self.client.post(url, data=pdf, headers=self.headers(1)).status_code, 403)
        pdf = {'arquivo': (BytesIO(b'%PDF-invalid'), 'fatura.pdf', 'application/pdf')}
        response = self.client.post(url, data=pdf, headers=self.headers(6))
        self.assertEqual((response.status_code, response.json['code']), (404, 'CLIENT_NOT_FOUND'))


if __name__ == '__main__':
    unittest.main()
