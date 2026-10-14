"""Fase 1: nonce OAuth, cookie de plataforma assinado, LogService transacional,
handler global de erro com request_id e escape da query do Drive."""
import os
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

_DATABASE_FILE = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_DATABASE_FILE.close()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402
from extensions import db  # noqa: E402
from models.empresa import Empresa  # noqa: E402
from models.log_entry import LogEntry  # noqa: E402
from models.user import User  # noqa: E402
from services import oauth_service  # noqa: E402
from services.drive_service import _escape_drive_literal  # noqa: E402
from services.log_service import LogService  # noqa: E402
from utils.auth import generate_token  # noqa: E402
try:
    from .support import IsolatedTestRuntime  # noqa: E402
except ImportError:
    from support import IsolatedTestRuntime  # noqa: E402


class Fase1HardeningTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepare_test_runtime(
            f"sqlite:///{_DATABASE_FILE.name.replace(chr(92), '/')}",
            'fase1-hardening-test-secret',
        )
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        with cls.app.app_context():
            db.create_all()
            company = Empresa(nome='A', slug='fase1-a')
            db.session.add(company)
            db.session.flush()
            platform = User(empresa_id=company.id, nome='Platform', email='platform@fase1.test', password_hash='x', role='owner', is_platform_admin=True)
            owner = User(empresa_id=company.id, nome='Owner', email='owner@fase1.test', password_hash='x', role='owner')
            db.session.add_all([platform, owner])
            db.session.commit()
            cls.empresa_id = company.id
            cls.platform_id = platform.id
            cls.owner_id = owner.id

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

    # --- OAuth: state amarrado ao navegador que iniciou ---------------------
    def test_oauth_callback_rejects_state_without_matching_nonce(self):
        with self.app.app_context():
            oauth_service._store_pending_state('state-x', 'verifier', self.empresa_id, oauth_service.hash_nonce('nonce-bom'))
            with self.assertRaises(ValueError) as ctx:
                oauth_service.handle_callback('https://hub.test/cb?code=1&state=state-x', 'state-x', nonce='nonce-errado')
            self.assertIn('outro navegador', str(ctx.exception))
            # state e de uso unico: segunda tentativa, mesmo com nonce certo, falha como expirado
            with self.assertRaises(ValueError) as ctx:
                oauth_service.handle_callback('https://hub.test/cb?code=1&state=state-x', 'state-x', nonce='nonce-bom')
            self.assertIn('expirado', str(ctx.exception))

    def test_oauth_callback_without_cookie_is_rejected_when_state_has_nonce(self):
        with self.app.app_context():
            oauth_service._store_pending_state('state-y', 'verifier', self.empresa_id, oauth_service.hash_nonce('n'))
            with self.assertRaises(ValueError):
                oauth_service.handle_callback('https://hub.test/cb?code=1&state=state-y', 'state-y', nonce=None)

    # --- Cookie de plataforma assinado -------------------------------------
    def test_raw_platform_view_cookie_is_ignored(self):
        client = self.app.test_client()
        client.set_cookie('hub_token', self._token(self.platform_id))
        client.set_cookie('hub_platform_view', str(self.empresa_id))
        response = client.get('/api/v1/clients')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()['code'], 'PLATFORM_TENANT_CONTEXT_REQUIRED')

    def test_platform_view_cookie_signed_for_another_user_is_ignored(self):
        from utils.auth import sign_platform_view
        client = self.app.test_client()
        client.set_cookie('hub_token', self._token(self.platform_id))
        with self.app.app_context():
            client.set_cookie('hub_platform_view', sign_platform_view(self.owner_id, self.empresa_id))
        self.assertEqual(client.get('/api/v1/clients').status_code, 403)

    # --- LogService nao comita transacao do chamador ------------------------
    def test_log_inside_pending_transaction_does_not_commit_callers_work(self):
        with self.app.app_context():
            empresa = Empresa(nome='Pendente', slug='fase1-pendente')
            db.session.add(empresa)
            db.session.flush()
            LogService.info(acao='teste', mensagem='dentro da transacao', metadados={'empresaId': self.empresa_id})
            db.session.rollback()
            self.assertIsNone(Empresa.query.filter_by(slug='fase1-pendente').first())
            self.assertIsNone(LogEntry.query.filter_by(mensagem='dentro da transacao').first())

    def test_log_with_clean_session_commits_immediately(self):
        with self.app.app_context():
            LogService.info(acao='teste', mensagem='sessao limpa', metadados={'empresaId': self.empresa_id})
            db.session.rollback()
            self.assertIsNotNone(LogEntry.query.filter_by(mensagem='sessao limpa').first())

    # --- Handler global ----------------------------------------------------
    def test_unhandled_exception_returns_generic_json_with_request_id(self):
        headers = {'Authorization': f'Bearer {self._token(self.owner_id)}', 'X-Request-ID': 'req-123'}
        with patch('routes.client_routes.list_clients', side_effect=RuntimeError('segredo interno')):
            response = self.app.test_client().get('/api/v1/clients', headers=headers)
        body = response.get_data(as_text=True)
        self.assertNotIn('segredo interno', body)
        self.assertEqual(response.headers.get('X-Request-ID'), 'req-123')
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_json()['code'], 'INTERNAL_ERROR')
        self.assertEqual(response.get_json()['requestId'], 'req-123')

    def test_unknown_route_returns_json_404(self):
        response = self.app.test_client().get('/api/v1/nao-existe', headers={'Authorization': f'Bearer {self._token(self.owner_id)}'})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()['code'], 'HTTP_404')
        self.assertTrue(response.headers.get('X-Request-ID'))

    # --- Drive query -------------------------------------------------------
    def test_drive_literal_escape_neutralizes_backslash_and_quote(self):
        self.assertEqual(_escape_drive_literal("O'Brien"), "O\\'Brien")
        self.assertEqual(_escape_drive_literal("a\\' or name contains 'x"), "a\\\\\\' or name contains \\'x")
        self.assertEqual(_escape_drive_literal("x\n\ty"), "xy")


if __name__ == '__main__':
    unittest.main()
