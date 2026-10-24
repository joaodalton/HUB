"""Contrato HTTP do dashboard do financeiro: RBAC, isolamento por tenant."""
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from extensions import db
from models.client import Client
from models.consumer_unit import ConsumerUnit, PlantConnection
from models.empresa import Empresa
from models.fatura import Fatura
from models.plant import Plant
from models.user import User
from utils.auth import generate_token

try:
    from .support import IsolatedTestRuntime
except ImportError:
    from support import IsolatedTestRuntime


class FinanceiroRoutesTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.prepare_test_runtime('sqlite:///' + (Path(cls.temp.name) / 'financeiro.db').as_posix(),
                                 'financeiro-routes-test', limiter_enabled=False)
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
            db.session.add(Empresa(id=tenant, nome=f'Empresa {tenant}', slug=f'financeiro-{tenant}'))
            db.session.add(Client(id=tenant, empresa_id=tenant, nome=f'Cliente {tenant}',
                                  cpf=str(tenant), email=f'{tenant}@example.test'))
            db.session.add(ConsumerUnit(id=tenant, empresa_id=tenant, client_id=tenant, codigo=f'UC{tenant}'))
            db.session.add(Plant(id=tenant, empresa_id=tenant, nome=f'Usina {tenant}',
                                 uc=f'UC-USINA-{tenant}', kw_pico=100))
            db.session.add(PlantConnection(id=tenant, empresa_id=tenant, consumer_unit_id=tenant,
                                           plant_id=tenant, percentual=100))
            db.session.add(Fatura(id=tenant, empresa_id=tenant, client_id=tenant, consumer_unit_id=tenant,
                                  concessionaria='Copel', competencia='2026-10', valor=1000,
                                  mes_vencimento=date(2026, 10, 10), asaas_status='received'))

        # Usina sem nenhuma UC conectada (tenant 10).
        db.session.add(Plant(id=11, empresa_id=10, nome='Usina sem conexao', uc='UC-USINA-11', kw_pico=50))

        users = ((1, 10, 'owner', False), (2, 10, 'financial', False), (3, 10, 'operator', False),
                 (4, 20, 'owner', False))
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

    def test_dashboard_retorna_totais_por_cliente_e_por_usina(self):
        response = self.client.get('/api/v1/financeiro/dashboard?competencia=2026-10',
                                   headers=self.headers(1))
        self.assertEqual(response.status_code, 200)
        body = response.json['data']
        self.assertIn('porCliente', body)
        self.assertIn('porUsina', body)

        cliente = next(c for c in body['porCliente'] if c['clienteId'] == 10)
        self.assertEqual(cliente['recebido'], '1000.00')
        self.assertEqual(cliente['pendente'], '0.00')

        usina = next(u for u in body['porUsina'] if u['usinaId'] == 10)
        self.assertEqual(usina['recebido'], '1000.00')
        self.assertIsNone(usina['repasseCalculado'])  # sem contrato configurado
        self.assertTrue(usina['contratoPendente'])

        # Usina sem nenhuma UC conectada nao deve ser tratada como pendencia de contrato.
        usina_sem_conexao = next(u for u in body['porUsina'] if u['usinaId'] == 11)
        self.assertEqual(usina_sem_conexao['recebido'], '0.00')
        self.assertIsNone(usina_sem_conexao['repasseCalculado'])
        self.assertFalse(usina_sem_conexao['contratoPendente'])
        self.assertTrue(usina_sem_conexao['semClientesConectados'])

        # Isolamento por tenant: dados da empresa 20 nao aparecem aqui.
        self.assertFalse(any(c['clienteId'] == 20 for c in body['porCliente']))
        self.assertFalse(any(u['usinaId'] == 20 for u in body['porUsina']))

    def test_dashboard_rejeita_competencia_com_formato_invalido(self):
        response = self.client.get('/api/v1/financeiro/dashboard?competencia=2026-10-01',
                                   headers=self.headers(1))
        self.assertEqual(response.status_code, 400)

    def test_dashboard_aceita_competencia_bem_formada(self):
        response = self.client.get('/api/v1/financeiro/dashboard?competencia=2026-10',
                                   headers=self.headers(1))
        self.assertEqual(response.status_code, 200)

    def test_dashboard_requer_permissao_financeiro_read(self):
        url = '/api/v1/financeiro/dashboard?competencia=2026-10'
        self.assertEqual(self.client.get(url).status_code, 401)
        self.assertEqual(self.client.get(url, headers=self.headers(3)).status_code, 403)
        self.assertEqual(self.client.get(url, headers=self.headers(2)).status_code, 200)


if __name__ == '__main__':
    unittest.main()
