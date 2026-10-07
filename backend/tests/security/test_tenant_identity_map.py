"""Known same-session tenant identity-map isolation regression (TC-1.2)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from flask import g  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app import create_app  # noqa: E402
from extensions import db  # noqa: E402
from models.client import Client  # noqa: E402
from models.empresa import Empresa  # noqa: E402
try:
    from ..support import IsolatedTestRuntime  # noqa: E402
except ImportError:
    from support import IsolatedTestRuntime  # noqa: E402


class TenantIdentityMapTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepare_test_runtime('sqlite://', 'tenant-identity-map-test')
        cls.app = create_app()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        cls.restore_test_runtime()

    def setUp(self):
        self.context = self.app.test_request_context('/')
        self.context.push()
        self.addCleanup(self.context.pop)
        db.create_all()
        company_a = Empresa(id=1, nome='A', slug='identity-a')
        company_b = Empresa(id=2, nome='B', slug='identity-b')
        client_a = Client(id=101, empresa_id=1, nome='Cliente A', cpf='idmap-a', email='a@test.local')
        db.session.add_all([company_a, company_b, client_a])
        db.session.commit()
        self.client_a_id = client_a.id
        self.addCleanup(db.drop_all)

    @unittest.expectedFailure
    def test_legacy_query_get_does_not_return_previous_tenants_identity(self):
        g.current_empresa_id = 1
        loaded = Client.query.get(self.client_a_id)
        self.assertEqual(loaded.empresa_id, 1)

        g.current_empresa_id = 2
        self.assertIsNone(Client.query.get(self.client_a_id))

    @unittest.expectedFailure
    def test_session_get_does_not_return_previous_tenants_identity(self):
        g.current_empresa_id = 1
        loaded = db.session.get(Client, self.client_a_id)
        self.assertEqual(loaded.empresa_id, 1)

        g.current_empresa_id = 2
        self.assertIsNone(db.session.get(Client, self.client_a_id))

    def test_explicit_tenant_filter_returns_no_foreign_client(self):
        g.current_empresa_id = 1
        self.assertIsNotNone(Client.query.get(self.client_a_id))

        g.current_empresa_id = 2
        result = db.session.scalars(
            select(Client).where(Client.id == self.client_a_id, Client.empresa_id == 2)
        ).first()
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
