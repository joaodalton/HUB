"""Contrato, filtros e isolamento tenant-scoped da Agenda derivada."""
import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path


_DATABASE_FILE = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_DATABASE_FILE.close()
os.environ['DATABASE_URL'] = f"sqlite:///{_DATABASE_FILE.name.replace(chr(92), '/')}"
os.environ['SECRET_KEY'] = 'agenda-service-test-secret'
os.environ['FLASK_DEBUG'] = 'true'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402
from config import Config  # noqa: E402
from extensions import db  # noqa: E402
from models.empresa import Empresa  # noqa: E402
from models.pendencia import Pendencia  # noqa: E402
from models.user import User  # noqa: E402
from utils.auth import generate_token  # noqa: E402

# Outros módulos de teste podem importar Config antes deste arquivo; mantenha o
# segredo de teste consistente mesmo quando a suíte for executada em conjunto.
Config.SECRET_KEY = os.environ['SECRET_KEY']


class AgendaServiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        with cls.app.app_context():
            db.create_all()
            empresa_a = Empresa(nome='Empresa A', slug='agenda-a')
            empresa_b = Empresa(nome='Empresa B', slug='agenda-b')
            db.session.add_all([empresa_a, empresa_b])
            db.session.flush()
            user_a = User(empresa_id=empresa_a.id, nome='Owner A', email='agenda-a@example.test', password_hash='x', role='owner')
            user_b = User(empresa_id=empresa_b.id, nome='Owner B', email='agenda-b@example.test', password_hash='x', role='owner')
            denied_user = User(empresa_id=empresa_a.id, nome='Denied', email='agenda-denied@example.test', password_hash='x', role='sem-permissao')
            db.session.add_all([user_a, user_b, denied_user])
            db.session.flush()
            db.session.add_all([
                Pendencia(empresa_id=empresa_a.id, tipo='pendencia', categoria='Sistema', origem='Manual', titulo='A no inicio', prioridade='alta', prazo=datetime(2026, 8, 1, 0, 0)),
                Pendencia(empresa_id=empresa_a.id, tipo='alerta', categoria='Sistema', origem='Sistema', titulo='A no fim', prioridade='media', prazo=datetime(2026, 8, 31, 23, 59)),
                Pendencia(empresa_id=empresa_a.id, tipo='pendencia', categoria='Sistema', origem='Manual', titulo='A fora', prioridade='baixa', prazo=datetime(2026, 9, 1)),
                Pendencia(empresa_id=empresa_b.id, tipo='pendencia', categoria='Sistema', origem='Manual', titulo='Nunca B', prioridade='critica', prazo=datetime(2026, 8, 15)),
            ])
            db.session.commit()
            cls.user_a_id = user_a.id
            cls.user_b_id = user_b.id
            cls.denied_user_id = denied_user.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        os.unlink(_DATABASE_FILE.name)

    def _get(self, user_id, query=''):
        with self.app.app_context():
            token = generate_token(user_id)
        return self.app.test_client().get(f'/api/v1/agenda{query}', headers={'Authorization': f'Bearer {token}'})

    def test_interval_is_inclusive_and_scoped_to_authenticated_tenant(self):
        response = self._get(self.user_a_id, '?inicio=2026-08-01&fim=2026-08-31&visao=mes')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']
        self.assertEqual(data['inicio'], '2026-08-01')
        self.assertEqual(data['fim'], '2026-08-31')
        self.assertEqual([item['titulo'] for item in data['itens']], ['A no inicio', 'A no fim'])
        self.assertEqual(data['itens'][1]['status'], 'aberta')
        self.assertTrue(all(item['fonte'] == 'pendencia' for item in data['itens']))
        self.assertNotIn('descricao', data['itens'][0])
        self.assertNotIn('metadados', data['itens'][0])
        self.assertNotIn('Nunca B', [item['titulo'] for item in data['itens']])

    def test_invalid_or_partial_interval_returns_bad_request(self):
        self.assertEqual(self._get(self.user_a_id, '?inicio=2026-08-01').status_code, 400)
        self.assertEqual(self._get(self.user_a_id, '?inicio=invalida&fim=2026-08-01').status_code, 400)
        self.assertEqual(self._get(self.user_a_id, '?inicio=2026-08-31&fim=2026-08-01').status_code, 400)
        self.assertEqual(self._get(self.user_a_id, '?visao=ano').status_code, 400)
        self.assertEqual(self._get(self.user_a_id, '?inicio=2026-01-01&fim=2026-12-31').status_code, 400)
        self.assertEqual(self._get(self.user_a_id, '?inicio=9999-12-31&fim=9999-12-31').status_code, 400)

    def test_other_tenant_only_sees_its_own_pendencia(self):
        response = self._get(self.user_b_id, '?inicio=2026-08-01&fim=2026-08-31')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['titulo'] for item in response.get_json()['data']['itens']], ['Nunca B'])

    def test_authentication_and_permission_are_required(self):
        self.assertEqual(self.app.test_client().get('/api/v1/agenda').status_code, 401)
        self.assertEqual(self._get(self.denied_user_id).status_code, 403)

    def test_lifecycle_and_prazo_change_are_reflected_without_sync(self):
        query = '?inicio=2026-08-01&fim=2026-08-31'
        with self.app.app_context():
            pendencia = Pendencia.query.filter_by(titulo='A no inicio').first()
            pendencia.status = 'resolvida'
            db.session.commit()
        self.assertNotIn('A no inicio', [item['titulo'] for item in self._get(self.user_a_id, query).get_json()['data']['itens']])
        with self.app.app_context():
            pendencia = Pendencia.query.filter_by(titulo='A no inicio').first()
            pendencia.status = 'aberta'
            pendencia.prazo = datetime(2026, 9, 1)
            db.session.commit()
        self.assertNotIn('A no inicio', [item['titulo'] for item in self._get(self.user_a_id, query).get_json()['data']['itens']])
        with self.app.app_context():
            pendencia = Pendencia.query.filter_by(titulo='A no inicio').first()
            pendencia.prazo = datetime(2026, 8, 15)
            db.session.commit()
        self.assertIn('A no inicio', [item['titulo'] for item in self._get(self.user_a_id, query).get_json()['data']['itens']])


if __name__ == '__main__':
    unittest.main()
