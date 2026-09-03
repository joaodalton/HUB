"""OAuth pode usar a raiz da conta, sem configuração manual de pasta."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

_DB = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_DB.close()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flask import g
from app import create_app
from config import Config
from extensions import db
from models.empresa import Empresa
from services.drive_service import _resolve_tenant_root_folder_id
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
            db.session.add_all([Empresa(nome='A', slug='drive-a'), Empresa(nome='B', slug='drive-b')])
            db.session.commit()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        os.unlink(_DB.name)
        cls.restore_test_runtime()

    def test_oauth_uses_connected_account_root_without_folder_id(self):
        original_root = Config.GOOGLE_DRIVE_ROOT_FOLDER_ID
        Config.GOOGLE_DRIVE_ROOT_FOLDER_ID = ''
        try:
            with self.app.test_request_context('/'):
                g.current_empresa_id = 1
                self.assertEqual(_resolve_tenant_root_folder_id(allow_account_root=True), '')
                with self.assertRaisesRegex(RuntimeError, 'Pasta raiz'):
                    _resolve_tenant_root_folder_id()
        finally:
            Config.GOOGLE_DRIVE_ROOT_FOLDER_ID = original_root


if __name__ == '__main__':
    unittest.main()
