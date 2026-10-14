"""Exclusao fisica de usuarios: permissao, tenant, owner, tokens e regressoes.
"""
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

_DATABASE_FILE = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_DATABASE_FILE.close()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402
from extensions import db  # noqa: E402
from models.empresa import Empresa  # noqa: E402
from models.user import User  # noqa: E402
from models.password_reset_token import PasswordResetToken  # noqa: E402
from models.import_preview import ImportPreview  # noqa: E402
from utils.auth import generate_token, hash_password  # noqa: E402
try:
    from .support import IsolatedTestRuntime  # noqa: E402
except ImportError:
    from support import IsolatedTestRuntime  # noqa: E402


class DeleteUserPhysicalTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepare_test_runtime(
            f"sqlite:///{_DATABASE_FILE.name.replace(chr(92), '/')}",
            'delete-user-test-secret',
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
                User(empresa_id=company_a.id, nome='Owner', email='owner@delete.test', password_hash='x', role='owner'),
                User(empresa_id=company_a.id, nome='Admin', email='admin@delete.test', password_hash='x', role='admin'),
                User(empresa_id=company_a.id, nome='Viewer', email='viewer@delete.test', password_hash='x', role='viewer'),
                User(empresa_id=company_b.id, nome='Other', email='other@delete.test', password_hash='x', role='viewer'),
            ]
            db.session.add_all(users)
            db.session.commit()
            cls.owner_id, cls.admin_id, cls.viewer_id, cls.other_id = [user.id for user in users]
            # usuario dedicado apenas ao teste de invalidacao de sessoes
            revoke = User(
                empresa_id=company_a.id,
                email='revoke@test',
                password_hash=hash_password('senha-test'),
                role='viewer',
            )
            db.session.add(revoke)
            db.session.commit()
            cls.revoke_user_id = revoke.id
            cls.revoke_actor_id = cls.admin_id
            cls.company_a_id = company_a.id

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

    def _delete(self, actor_id, target_id):
        return self.app.test_client().delete(
            f'/api/v1/users/{target_id}',
            headers={'Authorization': f'Bearer {self._token(actor_id)}'},
        )

    def test_unauthorized_actor_returns_401(self):
        # criar um usuario temporario para o actor (autor) nao autorizado.
        # usar o viewer de cena nao funciona porque ele foi apagado em tests
        # anteriores do mesmo banco.
        with self.app.app_context():
            actor = User(
                empresa_id=self.company_a_id,
                email='actor@delete.test',
                password_hash=hash_password('senha-test'),
                role='viewer',
            )
            db.session.add(actor)
            db.session.flush()
            actor_token = generate_token(actor.id)

        response = self.app.test_client().delete(
            f'/api/v1/users/{self.admin_id}',
            headers={'Authorization': f'Bearer {actor_token}'},
        )
        self.assertEqual(response.status_code, 401)
        with self.app.app_context():
            # o admin nao deve ter sido deletado
            self.assertIsNotNone(db.session.get(User, self.admin_id))

    def test_delete_other_company_returns_404(self):
        # o target pertence a outra empresa e nao deve ser encontrado
        response = self._delete(self.admin_id, self.other_id)
        self.assertEqual(response.status_code, 404)

    def test_delete_blocks_not_null_fk_records(self):
        # usuario possui import_preview (FK NOT NULL): bloqueia a exclusao
        with self.app.app_context():
            preview = ImportPreview(
                empresa_id=self.company_a_id,
                created_by_id=self.admin_id,
                arquivo_hash='a' * 64,
                plano={'clientes': [], 'ucs': [], 'usinas': []},
                status='pronto',
                expires_at=datetime.utcnow() + timedelta(days=1),
            )
            db.session.add(preview)
            db.session.commit()

        response = self._delete(self.admin_id, self.admin_id)
        self.assertEqual(response.status_code, 400)
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(User, self.admin_id))

    def test_delete_owner_is_protected(self):
        response = self._delete(self.admin_id, self.owner_id)
        self.assertEqual(response.status_code, 400)
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(User, self.owner_id))

    def test_delete_physical_user_removes_record(self):
        response = self._delete(self.admin_id, self.viewer_id)
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            self.assertIsNone(db.session.get(User, self.viewer_id))

    def test_delete_user_revokes_sessions_and_tokens(self):
        # gerar o token ANTES da inclusao e confirmar que o acesso antigo e
        # invalido depois
        old_token = self._token(self.revoke_user_id)
        response = self._delete(self.revoke_actor_id, self.revoke_user_id)
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            self.assertIsNone(db.session.get(User, self.revoke_user_id))
            self.assertEqual(
                db.session.query(PasswordResetToken).count(), 0,
            )
        get = self.app.test_client().get(
            '/api/v1/clients',
            headers={'Authorization': f'Bearer {old_token}'},
        )
        self.assertEqual(get.status_code, 401)
