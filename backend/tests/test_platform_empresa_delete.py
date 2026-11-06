"""Exclusao de empresa pela plataforma: so permite empresas vazias."""
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
from models.message_template import MessageTemplate  # noqa: E402
from models.user import User  # noqa: E402
from utils.auth import generate_token, hash_password  # noqa: E402
try:
    from .support import IsolatedTestRuntime  # noqa: E402
except ImportError:
    from support import IsolatedTestRuntime  # noqa: E402


class PlatformEmpresaDeleteTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepare_test_runtime(
            f"sqlite:///{_DB_FILE.name.replace(chr(92), '/')}",
            'platform-delete-secret',
            limiter_enabled=False,
        )
        cls.app = create_app()
        cls.app.config['TESTING'] = True

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.engine.dispose()
        os.unlink(_DB_FILE.name)
        cls._saved_environ = {
            key: value for key, value in cls._saved_environ.items() if len(value) <= 32767
        }
        cls.restore_test_runtime()

    def setUp(self):
        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()

    def _token(self, user_id):
        with self.app.app_context():
            return generate_token(user_id)

    def _auth(self, user_id):
        return {'Authorization': f'Bearer {self._token(user_id)}'}

    def _seed(self):
        with self.app.app_context():
            vazia = Empresa(nome='Empresa Vazia', slug='vazia', status='ativa')
            com_dado = Empresa(nome='Empresa Com Dado', slug='com-dado', status='ativa')
            db.session.add_all([vazia, com_dado])
            db.session.flush()
            platform_admin = User(
                empresa_id=None, nome='Admin', email='admin@delete.test',
                password_hash=hash_password('senha-segura'), role='viewer', is_platform_admin=True,
            )
            worker = User(
                empresa_id=None, nome='Worker', email='worker@delete.test',
                password_hash='x', role='viewer', is_platform_worker=True,
            )
            tenant_owner = User(
                empresa_id=com_dado.id, nome='Owner', email='owner@delete.test',
                password_hash='x', role='owner',
            )
            # MessageTemplate seedado automaticamente por qualquer empresa real
            # (nao deve bloquear a exclusao).
            db.session.add(MessageTemplate(
                empresa_id=vazia.id, canal='email', chave='boas-vindas', nome='Boas-vindas',
                assunto='Oi', corpo='Ola {{nome}}', variaveis_permitidas='nome', padrao=True, origem_chave='boas-vindas',
            ))
            db.session.add(LogEntry(
                empresa_id=vazia.id, nivel='info', acao='create', entidade='Empresa',
                entidade_id=vazia.id, mensagem='Empresa criada',
            ))
            db.session.add(Client(empresa_id=com_dado.id, nome='Cliente', cpf='111', email='c@client.test'))
            db.session.add_all([platform_admin, worker, tenant_owner])
            db.session.commit()
            return vazia.id, com_dado.id, platform_admin.id, worker.id, tenant_owner.id

    def test_platform_admin_deletes_empty_empresa(self):
        vazia_id, _com_dado_id, admin_id, _worker_id, _tenant_id = self._seed()
        client = self.app.test_client()

        response = client.delete(f'/api/v1/platform/empresas/{vazia_id}', headers=self._auth(admin_id))

        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            self.assertIsNone(db.session.get(Empresa, vazia_id))
            self.assertEqual(MessageTemplate.query.filter_by(empresa_id=vazia_id).count(), 0)
            deletion_log = LogEntry.query.filter_by(acao='empresa_deleted').first()
            self.assertIsNotNone(deletion_log)
            self.assertIsNone(deletion_log.empresa_id)
            self.assertEqual(deletion_log.metadados['empresaIdExcluida'], vazia_id)
            old_log = LogEntry.query.filter_by(acao='create', entidade_id=vazia_id).first()
            self.assertIsNotNone(old_log)
            self.assertIsNone(old_log.empresa_id)

    def test_blocks_deletion_when_empresa_has_data(self):
        _vazia_id, com_dado_id, admin_id, _worker_id, _tenant_id = self._seed()
        client = self.app.test_client()

        response = client.delete(f'/api/v1/platform/empresas/{com_dado_id}', headers=self._auth(admin_id))

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()['code'], 'EMPRESA_NOT_EMPTY')
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(Empresa, com_dado_id))

    def test_requires_platform_admin(self):
        vazia_id, _com_dado_id, _admin_id, worker_id, tenant_id = self._seed()
        client = self.app.test_client()

        self.assertEqual(
            client.delete(f'/api/v1/platform/empresas/{vazia_id}', headers=self._auth(worker_id)).status_code, 403,
        )
        self.assertEqual(
            client.delete(f'/api/v1/platform/empresas/{vazia_id}', headers=self._auth(tenant_id)).status_code, 403,
        )
        self.assertEqual(client.delete(f'/api/v1/platform/empresas/{vazia_id}').status_code, 401)
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(Empresa, vazia_id))

    def test_unknown_empresa_returns_404(self):
        _vazia_id, _com_dado_id, admin_id, _worker_id, _tenant_id = self._seed()
        client = self.app.test_client()

        response = client.delete('/api/v1/platform/empresas/999999', headers=self._auth(admin_id))

        self.assertEqual(response.status_code, 404)


if __name__ == '__main__':
    unittest.main()
