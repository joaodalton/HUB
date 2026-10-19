"""Acesso de platform worker: flag global somente leitura e isolamento."""
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
from models.user import User  # noqa: E402
from utils.auth import generate_token, hash_password  # noqa: E402
try:
    from .support import IsolatedTestRuntime  # noqa: E402
except ImportError:
    from support import IsolatedTestRuntime  # noqa: E402


class PlatformWorkerBoundaryTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepare_test_runtime(
            f"sqlite:///{_DB_FILE.name.replace(chr(92), '/')}",
            'platform-worker-secret',
            limiter_enabled=False,
        )
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        with cls.app.app_context():
            db.create_all()
            a = Empresa(nome='Empresa Worker A', slug='worker-a', status='ativa')
            db.session.add(a)
            db.session.flush()
            owner = User(empresa_id=a.id, nome='Owner', email='owner@boundary-worker.test',
                         password_hash=hash_password('senha-segura'), role='owner')
            worker = User(empresa_id=a.id, nome='Worker', email='worker@boundary-worker.test',
                          password_hash=hash_password('senha-segura'), role='viewer',
                          is_platform_worker=True)
            db.session.add_all([owner, worker])
            b = Empresa(nome='Empresa Worker B', slug='worker-b', status='ativa')
            db.session.add(b)
            db.session.flush()
            db.session.add(Client(empresa_id=a.id, nome='Cliente A', cpf='111', email='a@client.test'))
            db.session.add(Client(empresa_id=b.id, nome='Cliente B', cpf='222', email='b@client.test'))
            db.session.commit()
            cls.a_id = a.id
            cls.b_id = b.id
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

    def test_to_dict_exposes_is_platform_worker_default_false(self):
        with self.app.app_context():
            user = User.query.filter_by(email='owner@boundary-worker.test').first()
            self.assertEqual(user.to_dict()['isPlatformWorker'], False)

    def _token(self, user_id):
        with self.app.app_context():
            return generate_token(user_id)

    def _auth(self, user_id):
        return {'Authorization': f'Bearer {self._token(user_id)}'}

    def _view_cookie(self, user_id, empresa_id):
        from utils.auth import sign_platform_view
        with self.app.app_context():
            return sign_platform_view(user_id, empresa_id)

    def test_worker_can_enter_and_read_but_not_write(self):
        # Exercita o gate e o bloqueio de escrita do middleware diretamente
        # via cookie de view assinado (mesma tecnica de test_platform_boundary.py),
        # em vez de passar por POST /platform/empresas/<id>/entrar: essa rota
        # ainda esta decorada so com @require_platform_admin() (a troca para
        # @require_platform_access() que tambem libera o worker e escopo da
        # Task 4, ainda nao mesclada) -- nao e responsabilidade deste arquivo
        # (utils/auth.py) e nao deve ser alterada aqui.
        client = self.app.test_client()
        client.set_cookie('hub_token', self._token(self.worker_id))
        client.set_cookie('hub_csrf', 'csrf')
        client.set_cookie('hub_platform_view', self._view_cookie(self.worker_id, self.a_id))
        csrf = {'X-CSRF-Token': 'csrf'}
        self.assertEqual([row['nome'] for row in client.get('/api/v1/clients').get_json()['data']], ['Cliente A'])
        blocked = client.post('/api/v1/clients', json={'nome': 'X', 'cpf': '000', 'email': 'x@x.test'}, headers=csrf)
        self.assertEqual(blocked.status_code, 403)
        self.assertEqual(blocked.get_json()['code'], 'PLATFORM_WORKER_READ_ONLY')

    def _entered_worker_client(self):
        client = self.app.test_client()
        client.set_cookie('hub_token', self._token(self.worker_id))
        client.set_cookie('hub_csrf', 'csrf')
        client.set_cookie('hub_platform_view', self._view_cookie(self.worker_id, self.a_id))
        return client

    def test_worker_write_blocked_on_clients_put(self):
        client = self._entered_worker_client()
        response = client.put('/api/v1/clients/1', json={'nome': 'X', 'email': 'x@x.test'},
                              headers={'X-CSRF-Token': 'csrf'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()['code'], 'PLATFORM_WORKER_READ_ONLY')

    def test_worker_write_blocked_on_documents_post_and_delete(self):
        client = self._entered_worker_client()
        csrf = {'X-CSRF-Token': 'csrf'}
        post_response = client.post('/api/v1/documents', data={'nome': 'doc'}, headers=csrf)
        self.assertEqual(post_response.status_code, 403)
        self.assertEqual(post_response.get_json()['code'], 'PLATFORM_WORKER_READ_ONLY')
        delete_response = client.delete('/api/v1/documents/1', headers=csrf)
        self.assertEqual(delete_response.status_code, 403)
        self.assertEqual(delete_response.get_json()['code'], 'PLATFORM_WORKER_READ_ONLY')

    def test_worker_write_blocked_on_faturas_post(self):
        client = self._entered_worker_client()
        response = client.post('/api/v1/faturas', json={}, headers={'X-CSRF-Token': 'csrf'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()['code'], 'PLATFORM_WORKER_READ_ONLY')

    def test_worker_write_blocked_on_billing_calculations_execute(self):
        client = self._entered_worker_client()
        response = client.post('/api/v1/billing-calculations/invoices/1/execute',
                               headers={'X-CSRF-Token': 'csrf'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()['code'], 'PLATFORM_WORKER_READ_ONLY')

    def test_worker_can_read_platform_overview_and_company_list(self):
        client = self.app.test_client()
        headers = self._auth(self.worker_id)
        self.assertEqual(client.get('/api/v1/platform', headers=headers).status_code, 200)
        self.assertEqual(client.get('/api/v1/platform/empresas', headers=headers).status_code, 200)

    def test_worker_can_enter_and_exit_company_via_real_routes(self):
        # Worker pertence a A (casa); entra em B pela rota real e volta pra A.
        client = self.app.test_client()
        client.set_cookie('hub_token', self._token(self.worker_id))
        client.set_cookie('hub_csrf', 'csrf')
        csrf = {'X-CSRF-Token': 'csrf'}
        entered = client.post(f'/api/v1/platform/empresas/{self.b_id}/entrar', headers=csrf)
        self.assertEqual(entered.status_code, 200)
        self.assertEqual([row['nome'] for row in client.get('/api/v1/clients').get_json()['data']], ['Cliente B'])
        self.assertEqual(client.post('/api/v1/platform/sair', headers=csrf).status_code, 200)
        self.assertEqual(client.get('/api/v1/clients').get_json()['code'], 'PLATFORM_TENANT_CONTEXT_REQUIRED')

    def test_worker_without_entering_gets_tenant_context_required(self):
        client = self.app.test_client()
        outside = client.get('/api/v1/clients', headers=self._auth(self.worker_id))
        self.assertEqual(outside.status_code, 403)
        self.assertEqual(outside.get_json()['code'], 'PLATFORM_TENANT_CONTEXT_REQUIRED')

    def test_me_exposes_is_platform_worker_for_worker_account(self):
        client = self.app.test_client()
        response = client.get('/api/v1/auth/me', headers=self._auth(self.worker_id))
        self.assertEqual(response.get_json()['data']['isPlatformWorker'], True)


if __name__ == '__main__':
    unittest.main()
