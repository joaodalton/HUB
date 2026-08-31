"""Perfil cadastral da empresa ativa: RBAC, validação e isolamento."""
import os
import sys
import tempfile
import unittest
from pathlib import Path


_DATABASE_FILE = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_DATABASE_FILE.close()
os.environ['DATABASE_URL'] = f"sqlite:///{_DATABASE_FILE.name.replace(chr(92), '/')}"
os.environ['SECRET_KEY'] = 'empresa-atual-test-secret'
os.environ['FLASK_DEBUG'] = 'true'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402
from config import Config  # noqa: E402
from extensions import db  # noqa: E402
from models.empresa import Empresa  # noqa: E402
from models.user import User  # noqa: E402
from utils.auth import generate_token  # noqa: E402


Config.SECRET_KEY = os.environ['SECRET_KEY']


class EmpresaAtualTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        with cls.app.app_context():
            db.create_all()
            empresa_a = Empresa(nome='Empresa A', slug='empresa-atual-a', status='ativa', cnpj='11111111111111')
            empresa_b = Empresa(nome='Empresa B', slug='empresa-atual-b', status='suspensa', cnpj='22222222222222')
            db.session.add_all([empresa_a, empresa_b])
            db.session.flush()
            owner_a = User(empresa_id=empresa_a.id, nome='Owner A', email='empresa-owner-a@example.test', password_hash='x', role='owner')
            admin_a = User(empresa_id=empresa_a.id, nome='Admin A', email='empresa-admin-a@example.test', password_hash='x', role='admin')
            viewer_a = User(empresa_id=empresa_a.id, nome='Viewer A', email='empresa-viewer-a@example.test', password_hash='x', role='viewer')
            owner_b = User(empresa_id=empresa_b.id, nome='Owner B', email='empresa-owner-b@example.test', password_hash='x', role='owner')
            db.session.add_all([owner_a, admin_a, viewer_a, owner_b])
            db.session.commit()
            cls.owner_a_id, cls.admin_a_id = owner_a.id, admin_a.id
            cls.viewer_a_id, cls.owner_b_id = viewer_a.id, owner_b.id
            cls.empresa_a_id, cls.empresa_b_id = empresa_a.id, empresa_b.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        os.unlink(_DATABASE_FILE.name)

    def _request(self, method, user_id=None, body=None):
        headers = {}
        if user_id is not None:
            with self.app.app_context():
                headers['Authorization'] = f'Bearer {generate_token(user_id)}'
        return self.app.test_client().open('/api/v1/empresas/atual', method=method, headers=headers, json=body)

    def test_get_is_authenticated_and_scoped_to_current_empresa(self):
        self.assertEqual(self._request('GET').status_code, 401)
        owner_a = self._request('GET', self.owner_a_id)
        owner_b = self._request('GET', self.owner_b_id)
        self.assertEqual(owner_a.status_code, 200)
        self.assertEqual(owner_a.get_json()['data']['nome'], 'Empresa A')
        self.assertEqual(owner_b.get_json()['data']['nome'], 'Empresa B')
        self.assertNotIn('slug', owner_a.get_json()['data'])
        self.assertNotIn('status', owner_a.get_json()['data'])

    def test_only_owner_or_admin_can_update_and_protected_fields_are_rejected(self):
        self.assertEqual(self._request('PUT', self.viewer_a_id, {'nome': 'Tentativa'}).status_code, 403)
        updated = self._request('PUT', self.admin_a_id, {
            'nome': 'Empresa A Atualizada', 'razaoSocial': 'Empresa A LTDA',
            'cnpj': '11.111.111/1111-11', 'email': 'CONTATO@EXAMPLE.TEST', 'telefone': '(41) 99999-0000',
        })
        self.assertEqual(updated.status_code, 200)
        data = updated.get_json()['data']
        self.assertEqual(data['cnpj'], '11111111111111')
        self.assertEqual(data['email'], 'contato@example.test')
        protected = self._request('PUT', self.owner_a_id, {'slug': 'tomar-outra', 'status': 'suspensa', 'empresa_id': self.empresa_b_id})
        self.assertEqual(protected.status_code, 400)
        with self.app.app_context():
            empresa_a = db.session.get(Empresa, self.empresa_a_id)
            self.assertEqual(empresa_a.slug, 'empresa-atual-a')
            self.assertEqual(empresa_a.status, 'ativa')
            self.assertEqual(empresa_a.id, self.empresa_a_id)

    def test_invalid_profile_values_do_not_change_company(self):
        invalid = self._request('PUT', self.owner_b_id, {'nome': '', 'cnpj': '123'})
        self.assertEqual(invalid.status_code, 400)
        with self.app.app_context():
            empresa_b = db.session.get(Empresa, self.empresa_b_id)
            self.assertEqual(empresa_b.nome, 'Empresa B')
            self.assertEqual(empresa_b.cnpj, '22222222222222')


if __name__ == '__main__':
    unittest.main()
