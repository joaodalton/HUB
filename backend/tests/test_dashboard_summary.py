"""Cobertura mínima do resumo operacional e do isolamento entre tenants."""
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path


_DATABASE_FILE = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_DATABASE_FILE.close()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402
from config import Config  # noqa: E402
from extensions import db  # noqa: E402
from models.client import Client  # noqa: E402
from models.empresa import Empresa  # noqa: E402
from models.pendencia import Pendencia  # noqa: E402
from models.plant import Plant  # noqa: E402
from models.user import User  # noqa: E402
from utils.auth import generate_token  # noqa: E402
try:
    from .support import IsolatedTestRuntime  # noqa: E402
except ImportError:
    from support import IsolatedTestRuntime  # noqa: E402


class DashboardSummaryTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepare_test_runtime(
            f"sqlite:///{_DATABASE_FILE.name.replace(chr(92), '/')}",
            'dashboard-summary-test-secret',
        )
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        with cls.app.app_context():
            db.create_all()
            primeira = Empresa(nome='Empresa A', slug='empresa-a')
            segunda = Empresa(nome='Empresa B', slug='empresa-b')
            db.session.add_all([primeira, segunda])
            db.session.flush()
            cls.owner_a = User(empresa_id=primeira.id, nome='Owner A', email='owner-a@example.test', password_hash='x', role='owner')
            cls.financial_a = User(empresa_id=primeira.id, nome='Financial A', email='financial-a@example.test', password_hash='x', role='financial')
            cls.owner_b = User(empresa_id=segunda.id, nome='Owner B', email='owner-b@example.test', password_hash='x', role='owner')
            db.session.add_all([cls.owner_a, cls.financial_a, cls.owner_b])
            db.session.flush()
            db.session.add_all([
                Client(empresa_id=primeira.id, nome='Cliente A', cpf='00000000001', email='a@example.test', status='Ativo'),
                Client(empresa_id=segunda.id, nome='Cliente B', cpf='00000000002', email='b@example.test', status='Esperando usina'),
                Plant(empresa_id=primeira.id, nome='Usina A', uc='UA-1', kw_pico=10, status='Ativa'),
                Plant(empresa_id=segunda.id, nome='Usina B', uc='UB-1', kw_pico=20, status='Implantacao'),
                Pendencia(empresa_id=primeira.id, tipo='pendencia', categoria='Sistema', origem='Manual', titulo='Vencida A', prioridade='alta', prazo=datetime.utcnow() - timedelta(days=1)),
                Pendencia(empresa_id=primeira.id, tipo='pendencia', categoria='Sistema', origem='Manual', titulo='Proxima A', prioridade='media', prazo=datetime.utcnow() + timedelta(days=2)),
                Pendencia(empresa_id=primeira.id, tipo='pendencia', categoria='Sistema', origem='Manual', titulo='Resolvida A', prioridade='baixa', status='resolvida', resolved_at=datetime.utcnow()),
                Pendencia(empresa_id=segunda.id, tipo='pendencia', categoria='Sistema', origem='Manual', titulo='Somente B', prioridade='critica'),
                # Simula uma referência histórica inválida, criada antes da
                # validação explícita no service.
                Pendencia(empresa_id=primeira.id, tipo='pendencia', categoria='Sistema', origem='Manual', titulo='Responsável legado', prioridade='baixa', responsavel_id=cls.owner_b.id),
            ])
            db.session.commit()
            cls.owner_a_id = cls.owner_a.id
            cls.financial_a_id = cls.financial_a.id
            cls.owner_b_id = cls.owner_b.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        os.unlink(_DATABASE_FILE.name)
        cls.restore_test_runtime()

    def _get(self, user_id):
        with self.app.app_context():
            token = generate_token(user_id)
        client = self.app.test_client()
        client.set_cookie('hub_token', token, domain='localhost')
        return client.get('/api/v1/dashboard/resumo')

    def _token(self, user_id):
        with self.app.app_context():
            return generate_token(user_id)

    def test_summary_is_scoped_to_authenticated_tenant(self):
        response = self._get(self.owner_a_id)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']
        self.assertEqual(data['pendencias']['abertas'], 3)
        self.assertEqual(data['pendencias']['vencidas'], 1)
        self.assertEqual(data['pendencias']['vencendoEm7Dias'], 1)
        self.assertEqual(data['pendencias']['resolvidasNoMes'], 1)
        self.assertEqual(data['clientes']['total'], 1)
        self.assertEqual(data['usinas']['total'], 1)
        self.assertNotIn('Somente B', [item['titulo'] for item in data['pendencias']['fila']])
        legado = next(item for item in data['pendencias']['fila'] if item['titulo'] == 'Responsável legado')
        self.assertIsNone(legado['responsavelId'])
        self.assertIsNone(legado['responsavelNome'])

    def test_financial_role_does_not_receive_plant_metrics(self):
        response = self._get(self.financial_a_id)
        self.assertEqual(response.status_code, 200)
        usinas = response.get_json()['data']['usinas']
        self.assertFalse(usinas['disponivel'])
        self.assertIsNone(usinas['total'])
        self.assertIsNone(usinas['porStatus'])

    def test_cannot_assign_responsible_from_another_tenant(self):
        response = self.app.test_client().post(
            '/api/v1/pendencias',
            headers={'Authorization': f'Bearer {self._token(self.owner_a_id)}'},
            json={
                'titulo': 'Referência cruzada',
                'categoria': 'Sistema',
                'responsavelId': self.owner_b_id,
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['error'], 'Responsavel pertence a outra empresa.')


if __name__ == '__main__':
    unittest.main()
