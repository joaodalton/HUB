"""Ativacao de usuario: tipo estrito, RBAC, tenant e revogacao de sessao."""
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
from models.log_entry import LogEntry  # noqa: E402
from utils.auth import generate_token, hash_password  # noqa: E402
try:
    from .support import IsolatedTestRuntime  # noqa: E402
except ImportError:
    from support import IsolatedTestRuntime  # noqa: E402


class UserActivationSecurityTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepare_test_runtime(
            f"sqlite:///{_DATABASE_FILE.name.replace(chr(92), '/')}",
            'user-activation-test-secret',
        )
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        with cls.app.app_context():
            db.create_all()
            company_a = Empresa(nome='A', slug='activation-a')
            company_b = Empresa(nome='B', slug='activation-b')
            db.session.add_all([company_a, company_b])
            db.session.flush()
            users = [
                User(empresa_id=company_a.id, nome='Owner', email='owner@activation.test', password_hash='x', role='owner'),
                User(empresa_id=company_a.id, nome='Admin', email='admin@activation.test', password_hash='x', role='admin'),
                User(empresa_id=company_a.id, nome='Operator', email='operator@activation.test', password_hash='x', role='operator'),
                User(empresa_id=company_a.id, nome='Viewer', email='viewer@activation.test', password_hash='x', role='viewer'),
                User(empresa_id=company_a.id, nome='Forcado', email='forced@activation.test', password_hash=hash_password('senha-atual'), role='viewer', must_change_password=True),
                User(empresa_id=company_b.id, nome='Other', email='other@activation.test', password_hash='x', role='viewer'),
            ]
            db.session.add_all(users)
            db.session.commit()
            cls.owner_id, cls.admin_id, cls.operator_id, cls.viewer_id, cls.forced_id, cls.other_id = [user.id for user in users]

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        os.unlink(_DATABASE_FILE.name)
        cls.restore_test_runtime()

    def _token(self, user_id):
        with self.app.app_context():
            return generate_token(user_id)

    def _status(self, actor_id, target_id, ativo):
        return self.app.test_client().put(
            f'/api/v1/users/{target_id}/ativo',
            headers={'Authorization': f'Bearer {self._token(actor_id)}'},
            json={'ativo': ativo},
        )

    def test_requires_real_boolean_and_enforces_role_tenant_owner_and_self_guards(self):
        self.assertEqual(self._status(self.admin_id, self.viewer_id, 'false').status_code, 400)
        self.assertEqual(self._status(self.admin_id, self.viewer_id, 0).status_code, 400)
        self.assertEqual(self._status(self.operator_id, self.viewer_id, False).status_code, 403)
        self.assertEqual(self._status(self.admin_id, self.other_id, False).status_code, 404)
        self.assertEqual(self._status(self.admin_id, self.owner_id, False).status_code, 400)
        self.assertEqual(self._status(self.owner_id, self.owner_id, False).status_code, 400)

    def test_each_status_transition_revokes_prior_token(self):
        old_token = self._token(self.viewer_id)
        with self.app.app_context():
            initial_version = db.session.get(User, self.viewer_id).session_version

        self.assertEqual(self._status(self.admin_id, self.viewer_id, False).status_code, 200)
        self.assertEqual(
            self.app.test_client().get('/api/v1/clients', headers={'Authorization': f'Bearer {old_token}'}).status_code,
            401,
        )
        self.assertEqual(self._status(self.admin_id, self.viewer_id, True).status_code, 200)
        self.assertEqual(
            self.app.test_client().get('/api/v1/clients', headers={'Authorization': f'Bearer {old_token}'}).status_code,
            401,
        )
        with self.app.app_context():
            user = db.session.get(User, self.viewer_id)
            self.assertEqual(user.session_version, initial_version + 2)
            fresh_token = generate_token(user.id)
        self.assertEqual(
            self.app.test_client().get('/api/v1/clients', headers={'Authorization': f'Bearer {fresh_token}'}).status_code,
            200,
        )

    def test_forced_password_change_blocks_business_routes_then_refreshes_session(self):
        login = self.app.test_client().post(
            '/api/v1/auth/login', json={'email': 'forced@activation.test', 'senha': 'senha-atual'},
        )
        self.assertEqual(login.status_code, 200)
        self.assertTrue(login.get_json()['data']['mustChangePassword'])
        self.assertNotIn('password_hash', login.get_data(as_text=True))
        old_token = self._token(self.forced_id)
        blocked = self.app.test_client().get('/api/v1/clients', headers={'Authorization': f'Bearer {old_token}'})
        self.assertEqual(blocked.status_code, 403)
        self.assertEqual(blocked.get_json()['code'], 'PASSWORD_CHANGE_REQUIRED')
        self.assertEqual(
            self.app.test_client().get('/api/v1/auth/me', headers={'Authorization': f'Bearer {old_token}'}).status_code,
            200,
        )
        self.assertEqual(
            self.app.test_client().post(
                '/api/v1/auth/alterar-senha',
                headers={'Authorization': f'Bearer {old_token}'},
                json={'senhaAtual': 'errada', 'novaSenha': 'senha-nova'},
            ).status_code,
            400,
        )
        self.assertEqual(
            self.app.test_client().post(
                '/api/v1/auth/alterar-senha',
                headers={'Authorization': f'Bearer {old_token}'},
                json={'senhaAtual': 'senha-atual', 'novaSenha': 'curta'},
            ).status_code,
            400,
        )
        with self.app.app_context():
            initial_version = db.session.get(User, self.forced_id).session_version
        same_password = self.app.test_client().post(
            '/api/v1/auth/alterar-senha',
            headers={'Authorization': f'Bearer {old_token}'},
            json={'senhaAtual': 'senha-atual', 'novaSenha': 'senha-atual'},
        )
        self.assertEqual(same_password.status_code, 400)
        with self.app.app_context():
            user = db.session.get(User, self.forced_id)
            self.assertTrue(user.must_change_password)
            self.assertEqual(user.session_version, initial_version)
        refreshed_client = self.app.test_client()
        changed = refreshed_client.post(
            '/api/v1/auth/alterar-senha',
            headers={'Authorization': f'Bearer {old_token}'},
            json={'senhaAtual': 'senha-atual', 'novaSenha': 'senha-nova'},
        )
        self.assertEqual(changed.status_code, 200)
        self.assertFalse(changed.get_json()['data']['mustChangePassword'])
        self.assertNotIn('senha-nova', changed.get_data(as_text=True))
        self.assertEqual(
            self.app.test_client().get('/api/v1/clients', headers={'Authorization': f'Bearer {old_token}'}).status_code,
            401,
        )
        self.assertEqual(refreshed_client.get('/api/v1/clients').status_code, 200)
        with self.app.app_context():
            audit = LogEntry.query.filter_by(acao='password_changed').one()
            self.assertNotIn('senha-atual', str(audit.to_dict()))
            self.assertNotIn('senha-nova', str(audit.to_dict()))

    def test_forced_password_change_keeps_logout_available(self):
        token = self._token(self.forced_id)
        response = self.app.test_client().post(
            '/api/v1/auth/logout', headers={'Authorization': f'Bearer {token}'},
        )
        self.assertEqual(response.status_code, 200)


if __name__ == '__main__':
    unittest.main()
