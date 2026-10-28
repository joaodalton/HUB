"""OAuth pode usar a raiz da conta, sem configuração manual de pasta --
mas SO quando existe uma unica empresa no sistema (senao vaza cross-tenant)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

_DB = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_DB.close()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flask import g
from app import create_app
from config import Config
from extensions import db
from models.empresa import Empresa
from models.google_account import GoogleAccount
from models.setting import Setting
from models.pendencia import Pendencia
from services.drive_service import _build_oauth_credentials, _resolve_tenant_root_folder_id
try:
    from .support import IsolatedTestRuntime
except ImportError:
    from support import IsolatedTestRuntime


class OAuthDriveRootTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepare_test_runtime(f"sqlite:///{_DB.name.replace(chr(92), '/')}", 'oauth-drive-root-test')
        cls.app = create_app()
        with cls.app.app_context():
            db.create_all()
            db.session.add(Empresa(nome='A', slug='drive-a'))
            db.session.commit()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        os.unlink(_DB.name)
        cls.restore_test_runtime()

    def test_oauth_uses_connected_account_root_without_folder_id_when_single_empresa(self):
        original_root = Config.GOOGLE_DRIVE_ROOT_FOLDER_ID
        Config.GOOGLE_DRIVE_ROOT_FOLDER_ID = ''
        try:
            with self.app.test_request_context('/'):
                g.current_empresa_id = 1
                self.assertEqual(_resolve_tenant_root_folder_id(1), '')
        finally:
            Config.GOOGLE_DRIVE_ROOT_FOLDER_ID = original_root

    def test_multi_empresa_requires_explicit_root_folder(self):
        with self.app.app_context():
            db.session.add(Empresa(nome='B', slug='drive-b'))
            db.session.commit()
        try:
            with self.app.test_request_context('/'):
                g.current_empresa_id = 1
                with self.assertRaisesRegex(RuntimeError, 'Pasta raiz'):
                    _resolve_tenant_root_folder_id(1)
        finally:
            with self.app.app_context():
                Empresa.query.filter_by(slug='drive-b').delete()
                db.session.commit()

    def test_setting_root_folder_is_scoped_per_empresa(self):
        """Bug corrigido: Setting.query sem filtro por empresa_id entregava a
        pasta raiz de UM tenant pra outro. Confirma que cada empresa recebe
        apenas o seu proprio google_drive_root_folder_id."""
        with self.app.app_context():
            empresa_b = Empresa(nome='B', slug='drive-b-setting')
            db.session.add(empresa_b)
            db.session.commit()
            db.session.add_all([
                Setting(empresa_id=1, chave='google_drive_root_folder_id', valor='folder-empresa-1'),
                Setting(empresa_id=empresa_b.id, chave='google_drive_root_folder_id', valor='folder-empresa-b'),
            ])
            db.session.commit()
            empresa_b_id = empresa_b.id
        try:
            with self.app.test_request_context('/'):
                self.assertEqual(_resolve_tenant_root_folder_id(1), 'folder-empresa-1')
                self.assertEqual(_resolve_tenant_root_folder_id(empresa_b_id), 'folder-empresa-b')
        finally:
            with self.app.app_context():
                Setting.query.filter(Setting.chave == 'google_drive_root_folder_id').delete()
                Empresa.query.filter_by(slug='drive-b-setting').delete()
                db.session.commit()

    def test_oauth_credentials_are_scoped_per_empresa(self):
        """Bug corrigido: GoogleAccount.query sem filtro por empresa_id entregava
        a credencial OAuth de UM tenant pra outro. Confirma que cada empresa
        recupera somente a sua propria conta ativa (via refresh_token usado)."""
        with self.app.app_context():
            empresa_b = Empresa(nome='B', slug='drive-b-oauth')
            db.session.add(empresa_b)
            db.session.commit()

            account_1 = GoogleAccount(empresa_id=1, nome='Conta 1', email='a@x.com', is_active=True, scopes='s1')
            account_1.set_refresh_token('token-empresa-1')
            account_b = GoogleAccount(empresa_id=empresa_b.id, nome='Conta B', email='b@x.com', is_active=True, scopes='s1')
            account_b.set_refresh_token('token-empresa-b')
            db.session.add_all([account_1, account_b])
            db.session.commit()
            empresa_b_id = empresa_b.id

        try:
            with self.app.test_request_context('/'):
                with patch('services.drive_service.OAuthCredentials') as mock_credentials_cls:
                    mock_credentials_cls.return_value = Mock()

                    _build_oauth_credentials(1)
                    self.assertEqual(mock_credentials_cls.call_args.kwargs['refresh_token'], 'token-empresa-1')

                    _build_oauth_credentials(empresa_b_id)
                    self.assertEqual(mock_credentials_cls.call_args.kwargs['refresh_token'], 'token-empresa-b')
        finally:
            with self.app.app_context():
                GoogleAccount.query.delete()
                Empresa.query.filter_by(slug='drive-b-oauth').delete()
                db.session.commit()

    def test_refresh_failure_creates_pendencia_once_then_resolves_on_success(self):
        with self.app.app_context():
            account = GoogleAccount(empresa_id=1, nome='Conta', email='falha@x.com', is_active=True, scopes='s1')
            account.set_refresh_token('token-falha')
            db.session.add(account)
            db.session.commit()
            account_id, empresa_id = account.id, account.empresa_id

        try:
            with self.app.test_request_context('/'):
                with patch('services.drive_service.OAuthCredentials') as mock_credentials_cls:
                    broken = Mock()
                    broken.refresh.side_effect = Exception('token revogado')
                    mock_credentials_cls.return_value = broken

                    self.assertIsNone(_build_oauth_credentials(1))
                    self.assertIsNone(_build_oauth_credentials(1))  # dedupe: nao duplica a cada chamada

            with self.app.app_context():
                abertas = Pendencia.query.filter_by(empresa_id=empresa_id, categoria='Sistema', status='aberta').all()
                self.assertEqual(len([p for p in abertas if (p.metadados or {}).get('googleAccountId') == account_id]), 1)

            with self.app.test_request_context('/'):
                with patch('services.drive_service.OAuthCredentials') as mock_credentials_cls:
                    working = Mock()
                    mock_credentials_cls.return_value = working
                    self.assertIsNotNone(_build_oauth_credentials(1))

            with self.app.app_context():
                abertas = Pendencia.query.filter_by(empresa_id=empresa_id, categoria='Sistema', status='aberta').all()
                self.assertEqual([p for p in abertas if (p.metadados or {}).get('googleAccountId') == account_id], [])
        finally:
            with self.app.app_context():
                Pendencia.query.filter_by(empresa_id=empresa_id).delete()
                GoogleAccount.query.filter_by(id=account_id).delete()
                db.session.commit()


if __name__ == '__main__':
    unittest.main()
