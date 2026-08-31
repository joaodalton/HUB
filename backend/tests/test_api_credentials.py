"""Segredos de integracao: isolamento, redacao e ausencia de rede."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.fernet import Fernet


_DATABASE_FILE = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_DATABASE_FILE.close()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402
from config import Config  # noqa: E402
from extensions import db  # noqa: E402
from models.api_credential import ApiCredential  # noqa: E402
from models.empresa import Empresa  # noqa: E402
from models.log_entry import LogEntry  # noqa: E402
from models.user import User  # noqa: E402
from utils.auth import generate_token  # noqa: E402
try:
    from .support import IsolatedTestRuntime  # noqa: E402
except ImportError:
    from support import IsolatedTestRuntime  # noqa: E402


class ApiCredentialTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepare_test_runtime(
            f"sqlite:///{_DATABASE_FILE.name.replace(chr(92), '/')}",
            'api-credential-test-secret',
            encryption_key=Fernet.generate_key().decode(),
        )
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        with cls.app.app_context():
            db.create_all()
            empresa_a = Empresa(nome='Empresa A', slug='credencial-a')
            empresa_b = Empresa(nome='Empresa B', slug='credencial-b')
            db.session.add_all([empresa_a, empresa_b])
            db.session.flush()
            owner_a = User(empresa_id=empresa_a.id, nome='Owner A', email='cred-owner-a@example.test', password_hash='x', role='owner')
            owner_b = User(empresa_id=empresa_b.id, nome='Owner B', email='cred-owner-b@example.test', password_hash='x', role='owner')
            viewer_a = User(empresa_id=empresa_a.id, nome='Viewer A', email='cred-viewer-a@example.test', password_hash='x', role='viewer')
            db.session.add_all([owner_a, owner_b, viewer_a])
            db.session.commit()
            cls.owner_a_id, cls.owner_b_id, cls.viewer_a_id = owner_a.id, owner_b.id, viewer_a.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        os.unlink(_DATABASE_FILE.name)
        cls.restore_test_runtime()

    def _request(self, method, path, user_id=None, **kwargs):
        headers = kwargs.pop('headers', {})
        if user_id:
            with self.app.app_context():
                headers['Authorization'] = f'Bearer {generate_token(user_id)}'
        return self.app.test_client().open(path, method=method, headers=headers, **kwargs)

    def _create(self, user_id, nome='Principal', segredo='segredo-super-secreto'):
        return self._request('POST', '/api/v1/api-credentials', user_id, json={'provider': 'resend', 'nome': nome, 'segredo': segredo})

    def test_secret_is_encrypted_and_never_returned(self):
        response = self._create(self.owner_a_id)
        self.assertEqual(response.status_code, 201)
        payload = response.get_json()['data']
        self.assertEqual(set(payload), {'id', 'provider', 'nome', 'configurada', 'criadaEm', 'atualizadaEm'})
        self.assertNotIn('segredo', str(response.get_json()))
        with self.app.app_context():
            credential = ApiCredential.query.filter_by(id=payload['id']).first()
            self.assertNotEqual(credential.segredo_encrypted, 'segredo-super-secreto')
            self.assertEqual(credential.get_segredo(), 'segredo-super-secreto')
            ciphertext = credential.segredo_encrypted
        self.assertNotIn(ciphertext, response.get_data(as_text=True))
        self.assertNotIn(ciphertext, self._request('GET', f'/api/v1/api-credentials/{payload["id"]}', self.owner_a_id).get_data(as_text=True))
        self.assertNotIn(ciphertext, self._request('GET', '/api/v1/api-credentials', self.owner_a_id).get_data(as_text=True))

    def test_tenant_isolation_and_rbac(self):
        credential_id = self._create(self.owner_a_id, nome='Isolada').get_json()['data']['id']
        self.assertEqual(self._request('GET', '/api/v1/api-credentials', self.owner_b_id).get_json()['data'], [])
        self.assertEqual(self._request('GET', f'/api/v1/api-credentials/{credential_id}', self.owner_b_id).status_code, 404)
        self.assertEqual(self._request('DELETE', f'/api/v1/api-credentials/{credential_id}', self.owner_b_id).status_code, 404)
        self.assertEqual(self._request('GET', f'/api/v1/api-credentials/{credential_id}', self.owner_a_id).status_code, 200)
        self.assertEqual(self._request('PUT', f'/api/v1/api-credentials/{credential_id}', self.viewer_a_id, json={'nome': 'Tentativa'}).status_code, 403)
        self.assertEqual(self._request('GET', '/api/v1/api-credentials').status_code, 401)

    def test_update_without_secret_preserves_cipher_and_invalid_cipher_is_safe(self):
        credential_id = self._create(self.owner_a_id, nome='Atualizar', segredo='segredo-original').get_json()['data']['id']
        with self.app.app_context():
            credential = db.session.get(ApiCredential, credential_id)
            original_cipher = credential.segredo_encrypted
        response = self._request('PUT', f'/api/v1/api-credentials/{credential_id}', self.owner_a_id, json={'nome': 'Renomeada'})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(original_cipher, response.get_data(as_text=True))
        immutable = self._request('PUT', f'/api/v1/api-credentials/{credential_id}', self.owner_a_id, json={'provider': 'asaas'})
        self.assertEqual(immutable.status_code, 400)
        with self.app.app_context():
            credential = db.session.get(ApiCredential, credential_id)
            self.assertEqual(credential.segredo_encrypted, original_cipher)
            credential.segredo_encrypted = 'invalid-cipher'
            db.session.commit()
        failed = self._request('POST', f'/api/v1/api-credentials/{credential_id}/testar', self.owner_a_id)
        self.assertEqual(failed.status_code, 400)
        self.assertNotIn('invalid-cipher', failed.get_data(as_text=True))

    def test_missing_crypto_does_not_persist_partial_update_and_dry_run_never_uses_http(self):
        credential_id = self._create(self.owner_a_id, nome='Cifra', segredo='segredo-original').get_json()['data']['id']
        with self.app.app_context():
            original_cipher = db.session.get(ApiCredential, credential_id).segredo_encrypted
        original_key = Config.SECRET_ENCRYPTION_KEY
        Config.SECRET_ENCRYPTION_KEY = ''
        try:
            failed = self._request('PUT', f'/api/v1/api-credentials/{credential_id}', self.owner_a_id, json={'nome': 'Nao deve gravar', 'segredo': 'novo'})
            self.assertEqual(failed.status_code, 503)
        finally:
            Config.SECRET_ENCRYPTION_KEY = original_key
        with self.app.app_context():
            credential = db.session.get(ApiCredential, credential_id)
            self.assertEqual(credential.nome, 'Cifra')
            self.assertEqual(credential.segredo_encrypted, original_cipher)
        with patch('requests.sessions.Session.request', side_effect=AssertionError('rede proibida')):
            dry_run = self._request('POST', f'/api/v1/api-credentials/{credential_id}/testar', self.owner_a_id)
        self.assertEqual(dry_run.status_code, 200)
        self.assertEqual(dry_run.get_json()['data']['modo'], 'dry-run')

    def test_delete_creates_redacted_audit_in_same_database_transaction(self):
        credential_id = self._create(self.owner_a_id, nome='Apagar', segredo='nao-logar').get_json()['data']['id']
        response = self._request('DELETE', f'/api/v1/api-credentials/{credential_id}', self.owner_a_id)
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            self.assertIsNone(db.session.get(ApiCredential, credential_id))
            audit = LogEntry.query.filter_by(acao='api_credential_delete', entidade_id=credential_id).first()
            self.assertIsNotNone(audit)
            self.assertEqual(audit.metadados, {'provider': 'resend'})
            self.assertNotIn('nao-logar', str(audit.to_dict()))


if __name__ == '__main__':
    unittest.main()
