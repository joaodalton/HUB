"""Known same-session tenant identity-map isolation regression (TC-1.2)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from flask import g  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402

from app import create_app  # noqa: E402
from extensions import db  # noqa: E402
from models.client import Client  # noqa: E402
from models.consumer_unit import ConsumerUnit  # noqa: E402
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

    def test_legacy_query_get_does_not_return_previous_tenants_identity(self):
        g.current_empresa_id = 1
        loaded = Client.query.get(self.client_a_id)
        self.assertEqual(loaded.empresa_id, 1)

        g.current_empresa_id = 2
        self.assertIsNone(Client.query.get(self.client_a_id))

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

    def test_query_get_cycle_a_b_a_never_leaks_across_context_switches(self):
        for empresa_id in (1, 2, 1, 2, 1):
            g.current_empresa_id = empresa_id
            loaded = Client.query.get(self.client_a_id)
            if empresa_id == 1:
                self.assertEqual(loaded.empresa_id, 1)
            else:
                self.assertIsNone(loaded)

    def test_session_get_cycle_a_b_a_never_leaks_across_context_switches(self):
        for empresa_id in (1, 2, 1, 2, 1):
            g.current_empresa_id = empresa_id
            loaded = db.session.get(Client, self.client_a_id)
            if empresa_id == 1:
                self.assertEqual(loaded.empresa_id, 1)
            else:
                self.assertIsNone(loaded)

    def test_get_of_nonexistent_pk_is_none_regardless_of_tenant(self):
        g.current_empresa_id = 1
        self.assertIsNone(Client.query.get(999999))
        g.current_empresa_id = 2
        self.assertIsNone(Client.query.get(999999))

    def test_populate_existing_does_not_leak_across_tenants(self):
        g.current_empresa_id = 1
        loaded = db.session.get(Client, self.client_a_id, populate_existing=True)
        self.assertEqual(loaded.empresa_id, 1)

        g.current_empresa_id = 2
        self.assertIsNone(db.session.get(Client, self.client_a_id, populate_existing=True))

    def test_with_for_update_does_not_leak_across_tenants(self):
        g.current_empresa_id = 1
        loaded = db.session.get(Client, self.client_a_id, with_for_update=True)
        self.assertEqual(loaded.empresa_id, 1)
        db.session.commit()

        g.current_empresa_id = 2
        self.assertIsNone(db.session.get(Client, self.client_a_id, with_for_update=True))
        db.session.rollback()

    def test_relationship_loaded_before_switch_does_not_expose_tenant_a_object(self):
        uc = ConsumerUnit(id=201, empresa_id=1, client_id=self.client_a_id, codigo='UC-A')
        db.session.add(uc)
        db.session.commit()

        g.current_empresa_id = 1
        loaded = Client.query.get(self.client_a_id)
        self.assertEqual(len(loaded.ucs), 1)

        g.current_empresa_id = 2
        self.assertIsNone(Client.query.get(self.client_a_id))

    def test_refresh_under_switched_tenant_is_a_known_gap_outside_this_fix(self):
        """`Session.refresh()` emite `SELECT ... WHERE id = ?` sem passar
        pelo `with_loader_criteria` do `do_orm_execute` -- esse listener
        não é tocado por este fix (fora de escopo de ARCH-TENANT-1).
        Documentando o comportamento real em vez de assumir proteção que
        não existe, para não mascarar o gap numa futura regressão."""
        g.current_empresa_id = 1
        loaded = db.session.get(Client, self.client_a_id)
        self.assertIsNotNone(loaded)

        g.current_empresa_id = 2
        db.session.refresh(loaded)
        self.assertEqual(loaded.empresa_id, 1)

    def test_merge_under_switched_tenant_does_not_adopt_foreign_row(self):
        """merge() sob empresa errada não encontra o PK via `Session.get()`
        (nosso fix) e trata como linha nova -- o INSERT resultante colide
        com o PK já existente e é rejeitado pelo banco no flush, não pela
        sessão. A escrita acaba bloqueada, mas pela constraint, não pela
        aplicação; nenhum dado de outro tenant é adotado silenciosamente."""
        g.current_empresa_id = 1
        loaded = db.session.get(Client, self.client_a_id)
        db.session.expunge(loaded)

        g.current_empresa_id = 2
        merged = db.session.merge(loaded, load=True)
        self.assertEqual(merged.empresa_id, 1)
        with self.assertRaises(IntegrityError):
            db.session.flush()
        db.session.rollback()

    def test_write_on_object_obtained_under_wrong_tenant_get_is_blocked(self):
        g.current_empresa_id = 1
        self.assertIsNotNone(db.session.get(Client, self.client_a_id))

        g.current_empresa_id = 2
        foreign_lookup = db.session.get(Client, self.client_a_id)
        self.assertIsNone(foreign_lookup)
        db.session.add(Client(id=self.client_a_id, empresa_id=2, nome='Ataque', cpf='attack', email='x@test.local'))
        with self.assertRaises(Exception):
            db.session.flush()
        db.session.rollback()


if __name__ == '__main__':
    unittest.main()
