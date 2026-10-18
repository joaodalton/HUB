"""Gestao de contas platform_worker (CRUD exclusivo de platform_admin)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

_DB_FILE = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_DB_FILE.close()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402
from extensions import db  # noqa: E402
from models.empresa import Empresa  # noqa: E402
from models.user import User  # noqa: E402
from utils.auth import generate_token, hash_password  # noqa: E402
try:
    from .support import IsolatedTestRuntime  # noqa: E402
except ImportError:
    from support import IsolatedTestRuntime  # noqa: E402


class PlatformWorkerManagementTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepare_test_runtime(
            f"sqlite:///{_DB_FILE.name.replace(chr(92), '/')}",
            'platform-worker-management-secret',
            limiter_enabled=False,
        )
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        with cls.app.app_context():
            db.create_all()
            empresa = Empresa(nome='Empresa A', slug='worker-mgmt-a', status='ativa')
            db.session.add(empresa)
            db.session.flush()
            admin_platform = User(
                empresa_id=empresa.id, nome='Admin Plataforma', email='admin-platform@boundary.test',
                password_hash=hash_password('senha-segura'), role='viewer', is_platform_admin=True,
            )
            worker = User(
                empresa_id=empresa.id, nome='Worker', email='worker@boundary.test',
                password_hash=hash_password('senha-segura'), role='viewer', is_platform_worker=True,
            )
            db.session.add_all([admin_platform, worker])
            db.session.commit()
            cls.admin_platform_id = admin_platform.id
            cls.worker_id = worker.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        os.unlink(_DB_FILE.name)
        # O harness pode injetar payloads maiores que o limite de uma variavel
        # de ambiente do Windows; eles nao podem ser restaurados por os.environ.
        cls._saved_environ = {
            key: value for key, value in cls._saved_environ.items() if len(value) <= 32767
        }
        cls.restore_test_runtime()

    def _token(self, user_id):
        with self.app.app_context():
            return generate_token(user_id)

    def _auth(self, user_id):
        return {'Authorization': f'Bearer {self._token(user_id)}'}

    def test_admin_can_create_list_and_revoke_worker(self):
        client = self.app.test_client()
        headers = self._auth(self.admin_platform_id)
        create = client.post('/api/v1/platform/funcionarios', json={
            'nome': 'Fiscal', 'email': 'fiscal@boundary.test', 'senha': 'senha-segura'
        }, headers=headers)
        self.assertEqual(create.status_code, 201)
        worker_id = create.get_json()['data']['id']
        self.assertEqual(create.get_json()['data']['isPlatformWorker'], True)
        listing = client.get('/api/v1/platform/funcionarios', headers=headers)
        self.assertIn('fiscal@boundary.test', [row['email'] for row in listing.get_json()['data']])
        revoke = client.delete(f'/api/v1/platform/funcionarios/{worker_id}', headers=headers)
        self.assertEqual(revoke.status_code, 200)

    def test_create_worker_rejects_is_platform_admin_in_payload(self):
        client = self.app.test_client()
        headers = self._auth(self.admin_platform_id)
        response = client.post('/api/v1/platform/funcionarios', json={
            'nome': 'X', 'email': 'escalate@boundary.test', 'senha': 'senha-segura', 'is_platform_admin': True
        }, headers=headers)
        self.assertEqual(response.status_code, 400)

    def test_worker_cannot_manage_funcionarios(self):
        client = self.app.test_client()
        headers = self._auth(self.worker_id)
        self.assertEqual(client.get('/api/v1/platform/funcionarios', headers=headers).status_code, 403)
        self.assertEqual(client.post('/api/v1/platform/funcionarios', json={}, headers=headers).status_code, 403)

    def test_created_workers_share_the_internal_company(self):
        client = self.app.test_client()
        headers = self._auth(self.admin_platform_id)
        client.post('/api/v1/platform/funcionarios', json={
            'nome': 'Fiscal', 'email': 'fiscal2@boundary.test', 'senha': 'senha-segura'
        }, headers=headers)
        with self.app.app_context():
            internal = Empresa.query.filter_by(slug='plataforma-interna').first()
            self.assertIsNotNone(internal)
            worker = User.query.filter_by(email='fiscal2@boundary.test').first()
            self.assertEqual(worker.empresa_id, internal.id)


if __name__ == '__main__':
    unittest.main()
