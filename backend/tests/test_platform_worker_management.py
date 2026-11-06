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
from models.client import Client  # noqa: E402
from models.empresa import Empresa  # noqa: E402
from models.log_entry import LogEntry  # noqa: E402
from models.user import User  # noqa: E402
from utils.auth import generate_token, hash_password, sign_platform_view  # noqa: E402
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
            db.session.flush()
            # Empresa real de cliente, separada da "empresa casa" do admin/worker
            # acima -- usada pra simular o cookie de view ficando preso numa
            # empresa (hub_platform_view) enquanto o admin mexe em
            # /platform/funcionarios (rota "context-safe": nao exige ter
            # entrado numa empresa pra ser chamada).
            client_empresa = Empresa(nome='Empresa Cliente View', slug='worker-mgmt-client-view', status='ativa')
            db.session.add(client_empresa)
            db.session.flush()
            db.session.add(Client(empresa_id=client_empresa.id, nome='Cliente View', cpf='999', email='view@client.test'))
            # Empresa-alvo separada, usada so pelo teste de ciclo de vida
            # completo (criacao -> login -> troca de senha -> entrar -> ler
            # -> escrita bloqueada -> logout), pra nao colidir com os dados
            # das empresas usadas pelos outros testes desta classe.
            tenant_empresa = Empresa(nome='Empresa Tenant Lifecycle', slug='worker-mgmt-lifecycle', status='ativa')
            db.session.add(tenant_empresa)
            db.session.flush()
            db.session.add(Client(empresa_id=tenant_empresa.id, nome='Cliente Lifecycle', cpf='888', email='lifecycle@client.test'))
            db.session.commit()
            cls.admin_platform_id = admin_platform.id
            cls.worker_id = worker.id
            cls.client_empresa_id = client_empresa.id
            cls.tenant_empresa_id = tenant_empresa.id

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

    def _view_cookie(self, user_id, empresa_id):
        with self.app.app_context():
            return sign_platform_view(user_id, empresa_id)

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
        self.assertEqual(client.delete('/api/v1/platform/funcionarios/999999', headers=headers).status_code, 403)

    def test_create_worker_audit_log_does_not_leak_into_stale_view_cookie_company(self):
        # Admin tem um cookie hub_platform_view PRESO numa empresa de cliente
        # real (ex.: aba antiga aberta) enquanto chama /platform/funcionarios
        # (rota context-safe, nao exige ter "entrado" formalmente). O worker
        # criado nao pertence a nenhuma empresa, entao nenhum log de auditoria
        # pode ficar atribuido a empresa do cliente visualizada no cookie.
        client = self.app.test_client()
        headers = self._auth(self.admin_platform_id)
        client.set_cookie('hub_platform_view', self._view_cookie(self.admin_platform_id, self.client_empresa_id))
        create = client.post('/api/v1/platform/funcionarios', json={
            'nome': 'Fiscal Leak', 'email': 'fiscal-leak@boundary.test', 'senha': 'senha-segura'
        }, headers=headers)
        self.assertEqual(create.status_code, 201)
        worker_id = create.get_json()['data']['id']
        with self.app.app_context():
            worker = User.query.get(worker_id)
            self.assertIsNone(worker.empresa_id)
            leaked = [
                entry for entry in LogEntry.query.filter_by(
                    entidade='User', acao='create', empresa_id=self.client_empresa_id,
                ).all()
                if entry.metadados and entry.metadados.get('userId') == worker_id
            ]
            self.assertEqual(leaked, [])

    def test_revoke_worker_audit_log_does_not_leak_into_stale_view_cookie_company(self):
        client = self.app.test_client()
        headers = self._auth(self.admin_platform_id)
        create = client.post('/api/v1/platform/funcionarios', json={
            'nome': 'Fiscal Leak Revoke', 'email': 'fiscal-leak-revoke@boundary.test', 'senha': 'senha-segura'
        }, headers=headers)
        worker_id = create.get_json()['data']['id']

        client.set_cookie('hub_platform_view', self._view_cookie(self.admin_platform_id, self.client_empresa_id))
        revoke = client.delete(f'/api/v1/platform/funcionarios/{worker_id}', headers=headers)
        self.assertEqual(revoke.status_code, 200)
        with self.app.app_context():
            leaked = [
                entry for entry in LogEntry.query.filter_by(
                    entidade='User', acao='delete', empresa_id=self.client_empresa_id,
                ).all()
                if entry.metadados and entry.metadados.get('userId') == worker_id
            ]
            self.assertEqual(leaked, [])

    def test_worker_full_lifecycle_via_real_http_flow(self):
        # Fluxo HTTP completo, com cookies reais + header CSRF (como
        # test_platform_boundary.test_login_and_logout_clear_stale_view ja faz
        # pro admin): e' este teste que teria pego os findings 1-3 do review
        # final (deadlock de troca de senha, logout bloqueado, /auth/me nao
        # refletindo platformViewEmpresaId pro worker).
        admin_client = self.app.test_client()
        admin_login = admin_client.post('/api/v1/auth/login', json={
            'email': 'admin-platform@boundary.test', 'senha': 'senha-segura',
        })
        self.assertEqual(admin_login.status_code, 200)
        admin_csrf = admin_client.get_cookie('hub_csrf').value

        # (a) admin cria o worker via POST real.
        create = admin_client.post('/api/v1/platform/funcionarios', json={
            'nome': 'Fiscal Lifecycle', 'email': 'fiscal-lifecycle@boundary.test', 'senha': 'senha-temporaria',
        }, headers={'X-CSRF-Token': admin_csrf})
        self.assertEqual(create.status_code, 201)

        # (b) worker loga com a credencial recebida.
        worker_client = self.app.test_client()
        worker_login = worker_client.post('/api/v1/auth/login', json={
            'email': 'fiscal-lifecycle@boundary.test', 'senha': 'senha-temporaria',
        })
        self.assertEqual(worker_login.status_code, 200)
        csrf_1 = worker_client.get_cookie('hub_csrf').value

        # (c) troca de senha obrigatoria precisa ser possivel (finding 1:
        # sem o exemption em auth.py, isso 403 com PLATFORM_WORKER_READ_ONLY
        # antes mesmo de chegar no check de must_change_password).
        change_password = worker_client.post('/api/v1/auth/alterar-senha', json={
            'senhaAtual': 'senha-temporaria', 'novaSenha': 'nova-senha-segura',
        }, headers={'X-CSRF-Token': csrf_1})
        self.assertEqual(change_password.status_code, 200)
        old_token = worker_client.get_cookie('hub_token').value
        csrf_2 = worker_client.get_cookie('hub_csrf').value

        # (d) worker entra numa empresa pela rota real.
        entered = worker_client.post(
            f'/api/v1/platform/empresas/{self.tenant_empresa_id}/entrar',
            headers={'X-CSRF-Token': csrf_2},
        )
        self.assertEqual(entered.status_code, 200)

        # (e) finding 3: /auth/me agora precisa refletir platformViewEmpresaId
        # pro worker, nao so pro platform admin.
        me = worker_client.get('/api/v1/auth/me')
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.get_json()['data']['platformViewEmpresaId'], self.tenant_empresa_id)

        # (f) le dado de tenant normalmente.
        read = worker_client.get('/api/v1/clients')
        self.assertEqual(read.status_code, 200)
        self.assertEqual([row['nome'] for row in read.get_json()['data']], ['Cliente Lifecycle'])

        # (g) escrita continua bloqueada.
        blocked = worker_client.post('/api/v1/clients', json={
            'nome': 'X', 'cpf': '000', 'email': 'x@x.test',
        }, headers={'X-CSRF-Token': csrf_2})
        self.assertEqual(blocked.status_code, 403)
        self.assertEqual(blocked.get_json()['code'], 'PLATFORM_WORKER_READ_ONLY')

        # (h) finding 2: logout precisa funcionar e invalidar a sessao de
        # verdade no servidor (session_version bump), nao so limpar cookie.
        logout = worker_client.post('/api/v1/auth/logout', headers={'X-CSRF-Token': csrf_2})
        self.assertEqual(logout.status_code, 200)

        replay_client = self.app.test_client()
        replay_client.set_cookie('hub_token', old_token)
        replayed = replay_client.get('/api/v1/auth/me')
        self.assertEqual(replayed.status_code, 401)

    def test_created_workers_have_no_company(self):
        client = self.app.test_client()
        headers = self._auth(self.admin_platform_id)
        with self.app.app_context():
            pre_existing = Empresa.query.filter_by(slug='plataforma-interna').first()
        client.post('/api/v1/platform/funcionarios', json={
            'nome': 'Fiscal', 'email': 'fiscal2@boundary.test', 'senha': 'senha-segura'
        }, headers=headers)
        with self.app.app_context():
            worker = User.query.filter_by(email='fiscal2@boundary.test').first()
            self.assertIsNone(worker.empresa_id)
            self.assertEqual(
                Empresa.query.filter_by(slug='plataforma-interna').first(),
                pre_existing,
            )

    def test_admin_can_update_worker_name_and_email(self):
        client = self.app.test_client()
        headers = self._auth(self.admin_platform_id)
        create = client.post('/api/v1/platform/funcionarios', json={
            'nome': 'Fiscal Update', 'email': 'fiscal-update@boundary.test', 'senha': 'senha-segura'
        }, headers=headers)
        worker_id = create.get_json()['data']['id']

        update = client.put(f'/api/v1/platform/funcionarios/{worker_id}', json={
            'nome': 'Fiscal Atualizado', 'email': 'fiscal-update-novo@boundary.test',
        }, headers=headers)
        self.assertEqual(update.status_code, 200)
        self.assertEqual(update.get_json()['data']['nome'], 'Fiscal Atualizado')
        self.assertEqual(update.get_json()['data']['email'], 'fiscal-update-novo@boundary.test')

    def test_update_worker_password_invalidates_old_session(self):
        client = self.app.test_client()
        headers = self._auth(self.admin_platform_id)
        create = client.post('/api/v1/platform/funcionarios', json={
            'nome': 'Fiscal Senha', 'email': 'fiscal-senha@boundary.test', 'senha': 'senha-segura'
        }, headers=headers)
        worker_id = create.get_json()['data']['id']
        old_worker_headers = self._auth(worker_id)

        update = client.put(f'/api/v1/platform/funcionarios/{worker_id}', json={
            'senha': 'senha-nova-123',
        }, headers=headers)
        self.assertEqual(update.status_code, 200)

        stale = self.app.test_client().get('/api/v1/auth/me', headers=old_worker_headers)
        self.assertEqual(stale.status_code, 401)

    def test_update_worker_rejects_duplicate_email(self):
        client = self.app.test_client()
        headers = self._auth(self.admin_platform_id)
        client.post('/api/v1/platform/funcionarios', json={
            'nome': 'Fiscal Dup A', 'email': 'fiscal-dup-a@boundary.test', 'senha': 'senha-segura'
        }, headers=headers)
        create_b = client.post('/api/v1/platform/funcionarios', json={
            'nome': 'Fiscal Dup B', 'email': 'fiscal-dup-b@boundary.test', 'senha': 'senha-segura'
        }, headers=headers)
        worker_b_id = create_b.get_json()['data']['id']

        update = client.put(f'/api/v1/platform/funcionarios/{worker_b_id}', json={
            'email': 'fiscal-dup-a@boundary.test',
        }, headers=headers)
        self.assertEqual(update.status_code, 400)

    def test_update_worker_rejects_is_platform_admin_in_payload(self):
        client = self.app.test_client()
        headers = self._auth(self.admin_platform_id)
        create = client.post('/api/v1/platform/funcionarios', json={
            'nome': 'Fiscal Escalate', 'email': 'fiscal-escalate@boundary.test', 'senha': 'senha-segura'
        }, headers=headers)
        worker_id = create.get_json()['data']['id']

        update = client.put(f'/api/v1/platform/funcionarios/{worker_id}', json={
            'is_platform_admin': True,
        }, headers=headers)
        self.assertEqual(update.status_code, 400)

    def test_worker_cannot_update_funcionarios(self):
        client = self.app.test_client()
        headers = self._auth(self.worker_id)
        response = client.put(f'/api/v1/platform/funcionarios/{self.worker_id}', json={
            'nome': 'Tentativa',
        }, headers=headers)
        self.assertEqual(response.status_code, 403)

    def test_password_reset_works_for_worker_without_company(self):
        # Worker criado sem empresa (empresa_id=None) nao pode quebrar o fluxo
        # de "esqueci minha senha": renderizar_para_empresa(None, ...) cairia
        # em message_template_service.seed_for_empresa(None), que tenta
        # inserir MessageTemplate(empresa_id=None) -- coluna NOT NULL (
        # TenantMixin) -- e estourava IntegrityError (500 na rota publica).
        client = self.app.test_client()
        headers = self._auth(self.admin_platform_id)
        client.post('/api/v1/platform/funcionarios', json={
            'nome': 'Fiscal Reset', 'email': 'fiscal-reset@boundary.test', 'senha': 'senha-segura'
        }, headers=headers)
        with self.app.app_context():
            worker = User.query.filter_by(email='fiscal-reset@boundary.test').first()
            self.assertIsNone(worker.empresa_id)

        response = client.post('/api/v1/auth/esqueci-senha', json={'email': 'fiscal-reset@boundary.test'})
        self.assertEqual(response.status_code, 200)


if __name__ == '__main__':
    unittest.main()
