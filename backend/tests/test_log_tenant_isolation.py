"""Logs da empresa atual nunca incluem eventos de outro tenant."""
import sys
import unittest
from pathlib import Path

from flask import g

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402
from extensions import db  # noqa: E402
from models.empresa import Empresa  # noqa: E402
from services.log_service import LogService  # noqa: E402
try:
    from .support import IsolatedTestRuntime  # noqa: E402
except ImportError:
    from support import IsolatedTestRuntime  # noqa: E402


class LogTenantIsolationTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepare_test_runtime('sqlite://', 'log-tenant-isolation-test')
        cls.app = create_app()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        cls.restore_test_runtime()

    def setUp(self):
        self.context = self.app.app_context()
        self.context.push()
        self.addCleanup(self.context.pop)
        db.create_all()
        self.empresa_a = Empresa(nome='Empresa A', slug='logs-a')
        self.empresa_b = Empresa(nome='Empresa B', slug='logs-b')
        db.session.add_all([self.empresa_a, self.empresa_b])
        db.session.commit()
        self.addCleanup(db.drop_all)

    def test_list_recent_returns_only_the_current_company_events(self):
        LogService.info('evento_a', 'Evento da Empresa A', empresa_id=self.empresa_a.id)
        LogService.info('evento_b', 'Evento da Empresa B', empresa_id=self.empresa_b.id)

        with self.app.test_request_context():
            g.current_empresa_id = self.empresa_a.id
            self.assertEqual([entry['acao'] for entry in LogService.list_recent()], ['evento_a'])

        with self.app.test_request_context():
            g.current_empresa_id = self.empresa_b.id
            self.assertEqual([entry['acao'] for entry in LogService.list_recent()], ['evento_b'])


if __name__ == '__main__':
    unittest.main()
