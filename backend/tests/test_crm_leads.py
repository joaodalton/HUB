"""Sync PipeRun: isolamento por tenant, upsert idempotente e credencial ausente."""
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
from extensions import db  # noqa: E402
from models.api_credential import ApiCredential  # noqa: E402
from models.crm_lead import CrmLead  # noqa: E402
from models.empresa import Empresa  # noqa: E402
from models.user import User  # noqa: E402
from utils.auth import generate_token  # noqa: E402
try:
    from .support import IsolatedTestRuntime  # noqa: E402
except ImportError:
    from support import IsolatedTestRuntime  # noqa: E402


_DEAL_PAGE_1 = {
    'success': True,
    'data': [{
        'id': 123, 'title': 'Negocio PipeRun', 'status': 0, 'value': '1500.00',
        'created_at': '2026-01-01 10:00:00', 'updated_at': '2026-01-02 10:00:00',
    }],
    'meta': {'cursor': {'next': None}},
}


class CrmLeadTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepare_test_runtime(
            f"sqlite:///{_DATABASE_FILE.name.replace(chr(92), '/')}",
            'crm-lead-test-secret',
            encryption_key=Fernet.generate_key().decode(),
        )
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        with cls.app.app_context():
            db.create_all()
            empresa_a = Empresa(nome='Empresa A', slug='crm-a')
            empresa_b = Empresa(nome='Empresa B', slug='crm-b')
            db.session.add_all([empresa_a, empresa_b])
            db.session.flush()
            owner_a = User(empresa_id=empresa_a.id, nome='Owner A', email='crm-owner-a@example.test', password_hash='x', role='owner')
            owner_b = User(empresa_id=empresa_b.id, nome='Owner B', email='crm-owner-b@example.test', password_hash='x', role='owner')
            db.session.add_all([owner_a, owner_b])
            db.session.commit()
            cls.empresa_a_id, cls.empresa_b_id = empresa_a.id, empresa_b.id
            cls.owner_a_id, cls.owner_b_id = owner_a.id, owner_b.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        os.unlink(_DATABASE_FILE.name)
        cls.restore_test_runtime()

    def setUp(self):
        with self.app.app_context():
            CrmLead.query.delete()
            ApiCredential.query.delete()
            db.session.commit()

    def _request(self, method, path, user_id=None, **kwargs):
        headers = kwargs.pop('headers', {})
        if user_id:
            with self.app.app_context():
                headers['Authorization'] = f'Bearer {generate_token(user_id)}'
        return self.app.test_client().open(path, method=method, headers=headers, **kwargs)

    def _create_credential(self, empresa_id, token='piperun-token'):
        with self.app.app_context():
            credential = ApiCredential(empresa_id=empresa_id, provider='piperun', nome='Principal', segredo_encrypted='')
            credential.set_segredo(token)
            db.session.add(credential)
            db.session.commit()

    def test_sync_upserts_idempotently(self):
        self._create_credential(self.empresa_a_id)
        with patch('services.crm_lead_service.PipeRunClient') as client_cls:
            client_cls.return_value.listar_negocios.return_value = _DEAL_PAGE_1
            first = self._request('POST', '/api/v1/crm-leads/sincronizar', self.owner_a_id)
            self.assertEqual(first.status_code, 200)
            self.assertEqual(first.get_json()['data'], {'total_importados': 1, 'total_atualizados': 0})
            second = self._request('POST', '/api/v1/crm-leads/sincronizar', self.owner_a_id)
            self.assertEqual(second.status_code, 200)
            self.assertEqual(second.get_json()['data'], {'total_importados': 0, 'total_atualizados': 1})
        with self.app.app_context():
            leads = CrmLead.query.filter_by(empresa_id=self.empresa_a_id).all()
            self.assertEqual(len(leads), 1)
            self.assertEqual(leads[0].titulo, 'Negocio PipeRun')
            self.assertEqual(leads[0].external_id, '123')

    def test_tenant_isolation(self):
        self._create_credential(self.empresa_a_id)
        with patch('services.crm_lead_service.PipeRunClient') as client_cls:
            client_cls.return_value.listar_negocios.return_value = _DEAL_PAGE_1
            self._request('POST', '/api/v1/crm-leads/sincronizar', self.owner_a_id)
        self.assertEqual(len(self._request('GET', '/api/v1/crm-leads', self.owner_a_id).get_json()['data']), 1)
        self.assertEqual(self._request('GET', '/api/v1/crm-leads', self.owner_b_id).get_json()['data'], [])

    def test_missing_credential_returns_400(self):
        response = self._request('POST', '/api/v1/crm-leads/sincronizar', self.owner_a_id)
        self.assertEqual(response.status_code, 400)
        self.assertIn('PipeRun', response.get_json()['error'])


if __name__ == '__main__':
    unittest.main()
