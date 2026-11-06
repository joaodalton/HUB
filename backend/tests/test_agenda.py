import os
import sys
import tempfile
import unittest
from pathlib import Path

_DB = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_DB.close()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402
from extensions import db  # noqa: E402
from models.empresa import Empresa  # noqa: E402
from models.user import User  # noqa: E402
from utils.auth import generate_token  # noqa: E402
try:
    from .support import IsolatedTestRuntime  # noqa: E402
except ImportError:
    from support import IsolatedTestRuntime  # noqa: E402


class AgendaTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepare_test_runtime(f"sqlite:///{_DB.name.replace(chr(92), '/')}", 'agenda-test')
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        with cls.app.app_context():
            db.create_all()
            empresa_a, empresa_b = Empresa(nome='Agenda A', slug='agenda-a'), Empresa(nome='Agenda B', slug='agenda-b')
            db.session.add_all([empresa_a, empresa_b]); db.session.flush()
            user_a = User(empresa_id=empresa_a.id, nome='A', email='a@agenda.test', password_hash='x', role='owner')
            user_b = User(empresa_id=empresa_b.id, nome='B', email='b@agenda.test', password_hash='x', role='owner')
            db.session.add_all([user_a, user_b]); db.session.commit()
            cls.user_a, cls.user_b = user_a.id, user_b.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove(); db.drop_all(); db.engine.dispose()
        os.unlink(_DB.name)
        cls.restore_test_runtime()

    def request(self, user_id, path, method='GET', body=None):
        with self.app.app_context():
            headers = {'Authorization': f'Bearer {generate_token(user_id)}'}
        return self.app.test_client().open(path, method=method, headers=headers, json=body)

    def test_events_and_pending_tasks_share_the_tenant_agenda(self):
        pending = self.request(self.user_a, '/api/v1/pendencias', 'POST', {
            'titulo': 'Cobrar documento', 'categoria': 'Documentos', 'descricao': '', 'prioridade': 'alta', 'prazo': '2026-09-12T09:00',
        })
        self.assertEqual(pending.status_code, 201)
        event = self.request(self.user_a, '/api/v1/agenda/eventos', 'POST', {
            'titulo': 'Visita técnica', 'categoria': 'Operacional', 'inicio': '2026-09-12T14:00',
        })
        self.assertEqual(event.status_code, 201)
        event_id = event.get_json()['data']['id']

        agenda = self.request(self.user_a, '/api/v1/agenda?inicio=2026-09-12&fim=2026-09-12&visao=dia').get_json()['data']['itens']
        self.assertEqual({item['fonte'] for item in agenda}, {'pendencia', 'evento'})
        self.assertEqual(self.request(self.user_a, '/api/v1/pendencias').get_json()['data'][0]['titulo'], 'Cobrar documento')

        pendencia_id = pending.get_json()['data']['id']
        self.assertEqual(self.request(self.user_a, f'/api/v1/pendencias/{pendencia_id}', 'PUT', {'prazo': '2026-09-13T09:00'}).status_code, 200)
        self.assertEqual(self.request(self.user_a, '/api/v1/agenda?inicio=2026-09-12&fim=2026-09-12&visao=dia').get_json()['data']['itens'][0]['fonte'], 'evento')
        moved = self.request(self.user_a, '/api/v1/agenda?inicio=2026-09-13&fim=2026-09-13&visao=dia').get_json()['data']['itens']
        self.assertEqual(moved[0]['pendenciaId'], pendencia_id)

        self.assertEqual(self.request(self.user_b, f'/api/v1/agenda/eventos/{event_id}', 'PUT', {'titulo': 'Outro', 'categoria': 'Operacional', 'inicio': '2026-09-12T14:00'}).status_code, 404)
        self.assertEqual(self.request(self.user_b, '/api/v1/agenda?inicio=2026-09-12&fim=2026-09-12&visao=dia').get_json()['data']['itens'], [])

    def test_event_rejects_end_before_start(self):
        response = self.request(self.user_a, '/api/v1/agenda/eventos', 'POST', {
            'titulo': 'Inválido', 'categoria': 'Operacional', 'inicio': '2026-09-12T14:00', 'fim': '2026-09-12T13:00',
        })
        self.assertEqual(response.status_code, 400)


if __name__ == '__main__':
    unittest.main()
