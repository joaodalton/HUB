"""Autorizacao e isolamento do contexto administrativo da plataforma."""
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
from models.client import Client  # noqa: E402
from models.empresa import Empresa  # noqa: E402
from models.log_entry import LogEntry  # noqa: E402
from models.user import User  # noqa: E402
from utils.auth import generate_token, hash_password  # noqa: E402
try:
    from .support import IsolatedTestRuntime  # noqa: E402
except ImportError:
    from support import IsolatedTestRuntime  # noqa: E402


class PlatformBoundaryTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepare_test_runtime(
            f"sqlite:///{_DB_FILE.name.replace(chr(92), '/')}",
            'platform-boundary-secret',
            limiter_enabled=False,
        )
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        with cls.app.app_context():
            db.create_all()
            a = Empresa(nome='Empresa A', slug='boundary-a', status='ativa')
            b = Empresa(nome='Empresa B', slug='boundary-b', status='suspensa')
            db.session.add_all([a, b])
            db.session.flush()
            users = [
                User(empresa_id=a.id, nome='Platform', email='platform@boundary.test',
                     password_hash=hash_password('senha-segura'), role='viewer', is_platform_admin=True),
                User(empresa_id=a.id, nome='Owner', email='owner@boundary.test', password_hash='x', role='owner'),
                User(empresa_id=a.id, nome='Admin', email='admin@boundary.test', password_hash='x', role='admin'),
                User(empresa_id=a.id, nome='Operator', email='operator@boundary.test', password_hash='x', role='operator'),
                User(empresa_id=b.id, nome='Owner B', email='owner-b@boundary.test', password_hash='x', role='owner'),
            ]
            db.session.add_all(users)
            db.session.add_all([
                Client(empresa_id=a.id, nome='Cliente A', cpf='111', email='a@client.test'),
                Client(empresa_id=b.id, nome='Cliente B', cpf='222', email='b@client.test'),
            ])
            db.session.commit()
            cls.a_id, cls.b_id = a.id, b.id
            cls.platform_id = users[0].id
            cls.tenant_ids = [user.id for user in users[1:4]]

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

    def test_platform_authorization_for_anonymous_and_tenant_roles(self):
        client = self.app.test_client()
        self.assertEqual(client.get('/api/v1/platform').status_code, 401)
        for user_id in self.tenant_ids:
            self.assertEqual(client.get('/api/v1/platform', headers=self._auth(user_id)).status_code, 403)
            self.assertEqual(client.get('/api/v1/platform/empresas', headers=self._auth(user_id)).status_code, 403)
            self.assertEqual(client.post(f'/api/v1/platform/empresas/{self.b_id}/entrar', headers=self._auth(user_id)).status_code, 403)
        tenant_response = client.get('/api/v1/clients', headers=self._auth(self.tenant_ids[0]))
        self.assertEqual(tenant_response.status_code, 200)
        self.assertEqual([row['nome'] for row in tenant_response.get_json()['data']], ['Cliente A'])

    def test_overview_and_minimal_company_list(self):
        client = self.app.test_client()
        response = client.get('/api/v1/platform', headers=self._auth(self.platform_id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['data'], {'totalEmpresas': 2, 'totalUsuarios': 5})
        response = client.get('/api/v1/platform/empresas', headers=self._auth(self.platform_id))
        self.assertEqual(response.status_code, 200)
        rows = response.get_json()['data']
        self.assertEqual([row['totalUsuarios'] for row in rows], [4, 1])
        self.assertEqual(set(rows[0]), {'id', 'nome', 'slug', 'status', 'totalUsuarios', 'createdAt'})

    def test_existing_global_platform_apis_remain_available_without_tenant_view(self):
        client = self.app.test_client()
        platform_headers = self._auth(self.platform_id)
        self.assertEqual(client.get('/api/v1/regulatory-tariffs/status', headers=platform_headers).status_code, 200)
        self.assertEqual(client.get('/api/v1/config/database', headers=platform_headers).status_code, 200)
        self.assertEqual(client.get('/api/v1/empresas', headers=platform_headers).status_code, 200)

        tenant_headers = self._auth(self.tenant_ids[0])
        self.assertEqual(client.get('/api/v1/regulatory-tariffs/status', headers=tenant_headers).status_code, 403)
        self.assertEqual(client.get('/api/v1/config/database', headers=tenant_headers).status_code, 403)
        self.assertEqual(client.get('/api/v1/empresas', headers=tenant_headers).status_code, 403)

    def test_a_to_exit_to_b_has_no_stale_tenant_data(self):
        client = self.app.test_client()
        client.set_cookie('hub_token', self._token(self.platform_id))
        client.set_cookie('hub_csrf', 'csrf')
        csrf = {'X-CSRF-Token': 'csrf'}
        outside = client.get('/api/v1/clients')
        self.assertEqual(outside.status_code, 403)
        self.assertEqual(outside.get_json()['code'], 'PLATFORM_TENANT_CONTEXT_REQUIRED')
        missing_csrf = client.post(f'/api/v1/platform/empresas/{self.a_id}/entrar')
        self.assertEqual(missing_csrf.status_code, 403)
        self.assertIn('CSRF', missing_csrf.get_json()['error'])
        invalid_csrf = client.post(
            f'/api/v1/platform/empresas/{self.a_id}/entrar',
            headers={'X-CSRF-Token': 'errado'},
        )
        self.assertEqual(invalid_csrf.status_code, 403)
        self.assertIn('CSRF', invalid_csrf.get_json()['error'])
        entered = client.post(f'/api/v1/platform/empresas/{self.a_id}/entrar', headers=csrf)
        self.assertEqual(entered.status_code, 200)
        self.assertEqual(set(entered.get_json()['data']), {'id', 'nome', 'status'})
        self.assertEqual(client.get('/api/v1/auth/me').get_json()['data']['platformViewEmpresaId'], self.a_id)
        self.assertEqual([row['nome'] for row in client.get('/api/v1/clients').get_json()['data']], ['Cliente A'])
        self.assertEqual(client.post('/api/v1/platform/sair', headers=csrf).status_code, 200)
        self.assertIsNone(client.get('/api/v1/auth/me').get_json()['data']['platformViewEmpresaId'])
        after_exit = client.get('/api/v1/clients')
        self.assertEqual(after_exit.status_code, 403)
        self.assertEqual(after_exit.get_json()['code'], 'PLATFORM_TENANT_CONTEXT_REQUIRED')
        self.assertEqual(client.post(f'/api/v1/platform/empresas/{self.b_id}/entrar', headers=csrf).status_code, 200)
        self.assertEqual([row['nome'] for row in client.get('/api/v1/clients').get_json()['data']], ['Cliente B'])

    def test_platform_entry_audits_target_before_changing_view(self):
        client = self.app.test_client()
        client.set_cookie('hub_token', self._token(self.platform_id))
        client.set_cookie('hub_csrf', 'csrf')

        response = client.post(
            f'/api/v1/platform/empresas/{self.a_id}/entrar',
            headers={'X-CSRF-Token': 'csrf'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(client.get_cookie('hub_platform_view').value, str(self.a_id))
        self.assertEqual(client.get('/api/v1/auth/me').get_json()['data']['platformViewEmpresaId'], self.a_id)
        with self.app.app_context():
            event = LogEntry.query.filter_by(acao='platform_enter_tenant', entidade_id=self.a_id).order_by(LogEntry.id.desc()).first()
            self.assertIsNotNone(event)
            self.assertEqual(event.empresa_id, self.a_id)
            self.assertEqual(event.metadados['empresaId'], self.a_id)

    def test_platform_entry_audit_failure_preserves_previous_view(self):
        from unittest.mock import patch

        client = self.app.test_client()
        client.set_cookie('hub_token', self._token(self.platform_id))
        client.set_cookie('hub_csrf', 'csrf')
        client.set_cookie('hub_platform_view', str(self.a_id))

        with patch('services.log_service.db.session.commit', side_effect=RuntimeError('audit secret')):
            response = client.post(
                f'/api/v1/platform/empresas/{self.b_id}/entrar',
                headers={'X-CSRF-Token': 'csrf'},
            )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_json()['code'], 'PLATFORM_AUDIT_FAILED')
        self.assertNotIn('audit secret', response.get_data(as_text=True))
        self.assertEqual(client.get_cookie('hub_platform_view').value, str(self.a_id))
        self.assertEqual(client.get('/api/v1/auth/me').get_json()['data']['platformViewEmpresaId'], self.a_id)
        self.assertEqual([row['nome'] for row in client.get('/api/v1/clients').get_json()['data']], ['Cliente A'])

    def test_platform_exit_audits_viewed_company_before_clearing_view(self):
        client = self.app.test_client()
        client.set_cookie('hub_token', self._token(self.platform_id))
        client.set_cookie('hub_csrf', 'csrf')
        client.set_cookie('hub_platform_view', str(self.a_id))

        response = client.post('/api/v1/platform/sair', headers={'X-CSRF-Token': 'csrf'})

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(client.get_cookie('hub_platform_view'))
        self.assertIsNone(client.get('/api/v1/auth/me').get_json()['data']['platformViewEmpresaId'])
        with self.app.app_context():
            event = LogEntry.query.filter_by(acao='platform_exit_tenant', entidade_id=self.a_id).order_by(LogEntry.id.desc()).first()
            self.assertIsNotNone(event)
            self.assertEqual(event.empresa_id, self.a_id)
            self.assertEqual(event.metadados['empresaId'], self.a_id)

    def test_platform_exit_audit_failure_preserves_current_view(self):
        from unittest.mock import patch

        client = self.app.test_client()
        client.set_cookie('hub_token', self._token(self.platform_id))
        client.set_cookie('hub_csrf', 'csrf')
        client.set_cookie('hub_platform_view', str(self.a_id))

        with patch('services.log_service.db.session.commit', side_effect=RuntimeError('audit secret')):
            response = client.post('/api/v1/platform/sair', headers={'X-CSRF-Token': 'csrf'})

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_json()['code'], 'PLATFORM_AUDIT_FAILED')
        self.assertNotIn('audit secret', response.get_data(as_text=True))
        self.assertEqual(client.get_cookie('hub_platform_view').value, str(self.a_id))
        self.assertEqual(client.get('/api/v1/auth/me').get_json()['data']['platformViewEmpresaId'], self.a_id)
        self.assertEqual([row['nome'] for row in client.get('/api/v1/clients').get_json()['data']], ['Cliente A'])

    def test_invalid_id_and_public_prefix_method_bypass(self):
        client = self.app.test_client()
        self.assertEqual(client.post('/api/v1/platform/empresas/999999/entrar', headers=self._auth(self.platform_id)).status_code, 404)
        self.assertEqual(client.put(f'/api/v1/empresas/{self.a_id}', json={'nome': 'Ataque'}).status_code, 401)

    def test_login_and_logout_clear_stale_view(self):
        client = self.app.test_client()
        client.set_cookie('hub_platform_view', str(self.b_id))
        login = client.post('/api/v1/auth/login', json={'email': 'platform@boundary.test', 'senha': 'senha-segura'})
        self.assertEqual(login.status_code, 200)
        self.assertIsNone(client.get_cookie('hub_platform_view'))
        after_login = client.get('/api/v1/clients')
        self.assertEqual(after_login.status_code, 403)
        self.assertEqual(after_login.get_json()['code'], 'PLATFORM_TENANT_CONTEXT_REQUIRED')
        client.set_cookie('hub_platform_view', str(self.b_id))
        csrf = client.get_cookie('hub_csrf').value
        self.assertEqual(client.post('/api/v1/auth/logout', headers={'X-CSRF-Token': csrf}).status_code, 200)
        self.assertIsNone(client.get_cookie('hub_platform_view'))


if __name__ == '__main__':
    unittest.main()
