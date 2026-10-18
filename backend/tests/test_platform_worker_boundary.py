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
from models.empresa import Empresa  # noqa: E402
from models.user import User  # noqa: E402
from utils.auth import hash_password  # noqa: E402
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
            db.session.add(
                User(empresa_id=a.id, nome='Owner', email='owner@boundary-worker.test',
                     password_hash=hash_password('senha-segura'), role='owner')
            )
            db.session.commit()

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


if __name__ == '__main__':
    unittest.main()
