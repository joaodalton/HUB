"""Owner so e gerido por ele mesmo: admin nao troca senha/e-mail nem exclui o owner."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

_DATABASE_FILE = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_DATABASE_FILE.close()
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


class OwnerProtectionTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepare_test_runtime(
            f"sqlite:///{_DATABASE_FILE.name.replace(chr(92), '/')}",
            'owner-protection-test-secret',
        )
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        with cls.app.app_context():
            db.create_all()
            company = Empresa(nome='A', slug='owner-a')
            db.session.add(company)
            db.session.flush()
            users = [
                User(empresa_id=company.id, nome='Owner', email='owner@owner.test', password_hash='x', role='owner'),
                User(empresa_id=company.id, nome='Admin', email='admin@owner.test', password_hash='x', role='admin'),
                User(empresa_id=company.id, nome='Viewer', email='viewer@owner.test', password_hash='x', role='viewer'),
            ]
            db.session.add_all(users)
            db.session.commit()
            cls.owner_id, cls.admin_id, cls.viewer_id = [user.id for user in users]

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        os.unlink(_DATABASE_FILE.name)
        cls.restore_test_runtime()

    def _headers(self, user_id):
        with self.app.app_context():
            return {'Authorization': f'Bearer {generate_token(user_id)}'}

    def test_admin_cannot_change_owner_password_or_email(self):
        client = self.app.test_client()
        for payload in ({'senha': 'nova-senha-123'}, {'email': 'hijack@owner.test'}, {'nome': 'X'}):
            response = client.put(f'/api/v1/users/{self.owner_id}', headers=self._headers(self.admin_id), json=payload)
            self.assertEqual(response.status_code, 403, payload)
            self.assertEqual(response.get_json()['code'], 'OWNER_PROTECTED')
        with self.app.app_context():
            owner = db.session.get(User, self.owner_id)
            self.assertEqual(owner.email, 'owner@owner.test')
            self.assertEqual(owner.password_hash, 'x')

    def test_admin_cannot_delete_owner(self):
        response = self.app.test_client().delete(f'/api/v1/users/{self.owner_id}', headers=self._headers(self.admin_id))
        self.assertEqual(response.status_code, 400)
        with self.app.app_context():
            self.assertEqual(db.session.get(User, self.owner_id).status, 'ativo')

    def test_owner_edits_self_and_admin_still_manages_others(self):
        client = self.app.test_client()
        self.assertEqual(client.put(f'/api/v1/users/{self.owner_id}', headers=self._headers(self.owner_id), json={'nome': 'Dona'}).status_code, 200)
        self.assertEqual(client.put(f'/api/v1/users/{self.viewer_id}', headers=self._headers(self.admin_id), json={'nome': 'Viewer 2'}).status_code, 200)


if __name__ == '__main__':
    unittest.main()
