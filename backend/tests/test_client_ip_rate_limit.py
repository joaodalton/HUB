"""D1: client_ip() nao pode confiar em X-Forwarded-For (request.access_route),
que o proprio cliente escreve -- senao o rate limit de login e contornavel
trocando esse cabecalho a cada tentativa."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402
from extensions import db, client_ip  # noqa: E402
from models.empresa import Empresa  # noqa: E402
try:
    from .support import IsolatedTestRuntime  # noqa: E402
except ImportError:
    from support import IsolatedTestRuntime  # noqa: E402


class ClientIpRateLimitTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.prepare_test_runtime(
            f"sqlite:///{Path(cls.folder.name).as_posix()}/client_ip.db",
            'client-ip-rate-limit-test-secret',
            limiter_enabled=True,
        )
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        with cls.app.app_context():
            db.create_all()
            db.session.add(Empresa(nome='A', slug='client-ip-a'))
            db.session.commit()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()
        cls.folder.cleanup()
        cls.restore_test_runtime()

    def setUp(self):
        self.client = self.app.test_client()
        from extensions import limiter
        limiter.reset()

    def test_client_ip_ignores_forged_x_forwarded_for(self):
        with self.app.test_request_context(
            '/',
            headers={'X-Forwarded-For': '6.6.6.6, 203.0.113.9'},
            environ_base={'REMOTE_ADDR': '198.51.100.1'},
        ):
            self.assertEqual(client_ip(), '198.51.100.1')

    def test_login_rate_limit_not_bypassed_by_varying_x_forwarded_for(self):
        payload = {'email': 'nobody@example.com', 'senha': 'wrong-password'}
        for attempt in range(5):
            response = self.client.post(
                '/api/v1/auth/login',
                json=payload,
                headers={'X-Forwarded-For': f'10.0.0.{attempt}'},
            )
            self.assertEqual(response.status_code, 401)

        sixth = self.client.post(
            '/api/v1/auth/login',
            json=payload,
            headers={'X-Forwarded-For': '10.0.0.99'},
        )
        self.assertEqual(sixth.status_code, 429)


if __name__ == '__main__':
    unittest.main()
