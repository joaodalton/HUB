"""GET/PUT /api/v1/platform/configuracao (admin only) e fallback pro env var."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_DB_FILE = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_DB_FILE.close()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402
from config import Config  # noqa: E402
from extensions import db  # noqa: E402
from models.empresa import Empresa  # noqa: E402
from models.platform_configuracao import PlatformConfiguracao  # noqa: E402
from models.user import User  # noqa: E402
from services.platform_config_service import get_platform_asaas_credentials, get_signup_config  # noqa: E402
from utils.auth import generate_token, hash_password  # noqa: E402
try:
    from .support import IsolatedTestRuntime  # noqa: E402
except ImportError:
    from support import IsolatedTestRuntime  # noqa: E402


class PlatformConfiguracaoTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepare_test_runtime(
            f"sqlite:///{_DB_FILE.name.replace(chr(92), '/')}",
            'platform-configuracao-secret',
            limiter_enabled=False,
        )
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        with cls.app.app_context():
            db.create_all()
            empresa = Empresa(nome='Empresa A', slug='config-a', status='ativa')
            db.session.add(empresa)
            db.session.flush()
            admin = User(
                empresa_id=empresa.id, nome='Admin Plataforma', email='admin-config@boundary.test',
                password_hash=hash_password('senha-segura'), role='viewer', is_platform_admin=True,
            )
            tenant_user = User(
                empresa_id=empresa.id, nome='Tenant', email='tenant-config@boundary.test',
                password_hash=hash_password('senha-segura'), role='owner',
            )
            db.session.add_all([admin, tenant_user])
            db.session.commit()
            cls.admin_id = admin.id
            cls.tenant_id = tenant_user.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        os.unlink(_DB_FILE.name)
        cls._saved_environ = {
            key: value for key, value in cls._saved_environ.items() if len(value) <= 32767
        }
        cls.restore_test_runtime()

    def setUp(self):
        with self.app.app_context():
            PlatformConfiguracao.query.delete()
            db.session.commit()

    def _token(self, user_id):
        with self.app.app_context():
            return generate_token(user_id)

    def _auth(self, user_id):
        return {'Authorization': f'Bearer {self._token(user_id)}'}

    def test_get_requires_authentication(self):
        client = self.app.test_client()
        self.assertEqual(client.get('/api/v1/platform/configuracao').status_code, 401)

    def test_get_requires_platform_admin(self):
        client = self.app.test_client()
        response = client.get('/api/v1/platform/configuracao', headers=self._auth(self.tenant_id))
        self.assertEqual(response.status_code, 403)

    def test_get_as_admin_returns_shape_without_plain_secret(self):
        client = self.app.test_client()
        response = client.get('/api/v1/platform/configuracao', headers=self._auth(self.admin_id))
        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']
        self.assertEqual(set(data), {
            'asaasApiBaseUrl', 'asaasApiKeyConfigurada', 'asaasWebhookTokenConfigurada',
            'signupCodeConfigurada', 'signupEmpresaId',
        })
        self.assertFalse(data['asaasApiKeyConfigurada'])
        self.assertFalse(data['asaasWebhookTokenConfigurada'])
        self.assertFalse(data['signupCodeConfigurada'])

    def test_put_updates_and_persists(self):
        client = self.app.test_client()
        headers = self._auth(self.admin_id)
        response = client.put('/api/v1/platform/configuracao', json={
            'asaasApiBaseUrl': 'https://api-sandbox.asaas.com/v3',
            'asaasApiKey': 'super-secret-key',
            'asaasWebhookToken': 'super-secret-token',
            'signupCode': 'familia-123',
            'signupEmpresaId': 7,
        }, headers=headers)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']
        self.assertEqual(data['asaasApiBaseUrl'], 'https://api-sandbox.asaas.com/v3')
        self.assertTrue(data['asaasApiKeyConfigurada'])
        self.assertTrue(data['asaasWebhookTokenConfigurada'])
        self.assertTrue(data['signupCodeConfigurada'])
        self.assertEqual(data['signupEmpresaId'], 7)
        self.assertNotIn('super-secret-key', response.get_data(as_text=True))
        self.assertNotIn('super-secret-token', response.get_data(as_text=True))
        self.assertNotIn('familia-123', response.get_data(as_text=True))

        with self.app.app_context():
            config = PlatformConfiguracao.get_or_create()
            self.assertEqual(config.get_asaas_api_key(), 'super-secret-key')
            self.assertEqual(config.get_asaas_webhook_token(), 'super-secret-token')
            self.assertEqual(config.get_signup_code(), 'familia-123')
            self.assertEqual(config.signup_empresa_id, 7)

    def test_put_rejects_invalid_asaas_url(self):
        client = self.app.test_client()
        response = client.put('/api/v1/platform/configuracao', json={
            'asaasApiBaseUrl': 'https://malicious.example.com/v3',
        }, headers=self._auth(self.admin_id))
        self.assertEqual(response.status_code, 400)

    def test_put_partial_update_does_not_erase_other_fields(self):
        client = self.app.test_client()
        headers = self._auth(self.admin_id)
        client.put('/api/v1/platform/configuracao', json={
            'asaasApiKey': 'key-1', 'signupCode': 'code-1',
        }, headers=headers)
        response = client.put('/api/v1/platform/configuracao', json={
            'asaasWebhookToken': 'token-1',
        }, headers=headers)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']
        self.assertTrue(data['asaasApiKeyConfigurada'])
        self.assertTrue(data['signupCodeConfigurada'])
        self.assertTrue(data['asaasWebhookTokenConfigurada'])

    def test_put_empty_string_clears_field(self):
        client = self.app.test_client()
        headers = self._auth(self.admin_id)
        client.put('/api/v1/platform/configuracao', json={'signupCode': 'code-1'}, headers=headers)
        response = client.put('/api/v1/platform/configuracao', json={'signupCode': ''}, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()['data']['signupCodeConfigurada'])
        with self.app.app_context():
            self.assertIsNone(PlatformConfiguracao.get_or_create().get_signup_code())

    def test_put_rejects_non_integer_signup_empresa_id(self):
        client = self.app.test_client()
        response = client.put('/api/v1/platform/configuracao', json={
            'signupEmpresaId': 'abc',
        }, headers=self._auth(self.admin_id))
        self.assertEqual(response.status_code, 400)

    def test_service_falls_back_to_env_var_when_table_empty(self):
        with self.app.app_context():
            with patch.object(Config, 'PLATFORM_ASAAS_API_BASE_URL', 'https://api-sandbox.asaas.com/v3'), \
                    patch.object(Config, 'PLATFORM_ASAAS_API_KEY', 'env-key'), \
                    patch.object(Config, 'PLATFORM_ASAAS_WEBHOOK_TOKEN', 'env-token'):
                credentials = get_platform_asaas_credentials()
            self.assertEqual(credentials['base_url'], 'https://api-sandbox.asaas.com/v3')
            self.assertEqual(credentials['api_key'], 'env-key')
            self.assertEqual(credentials['webhook_token'], 'env-token')

            with patch.object(Config, 'SIGNUP_CODE', 'env-code'), patch.object(Config, 'SIGNUP_EMPRESA_ID', '3'):
                signup = get_signup_config()
            self.assertEqual(signup['code'], 'env-code')
            self.assertEqual(signup['empresa_id'], '3')

    def test_service_prefers_table_over_env_var_once_configured(self):
        client = self.app.test_client()
        client.put('/api/v1/platform/configuracao', json={
            'asaasApiKey': 'table-key', 'signupCode': 'table-code', 'signupEmpresaId': 9,
        }, headers=self._auth(self.admin_id))
        with self.app.app_context():
            with patch.object(Config, 'PLATFORM_ASAAS_API_KEY', 'env-key'):
                self.assertEqual(get_platform_asaas_credentials()['api_key'], 'table-key')
            with patch.object(Config, 'SIGNUP_CODE', 'env-code'), patch.object(Config, 'SIGNUP_EMPRESA_ID', '3'):
                signup = get_signup_config()
                self.assertEqual(signup['code'], 'table-code')
                self.assertEqual(signup['empresa_id'], 9)


if __name__ == '__main__':
    unittest.main()
