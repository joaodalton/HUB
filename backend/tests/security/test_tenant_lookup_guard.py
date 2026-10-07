"""Guards for tenant-scoped primary-key lookups."""

import ast
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from flask import Flask, g  # noqa: E402

import app as _app_module  # noqa: F401,E402
from extensions import TenantMixin, db  # noqa: E402
from models.category import Category  # noqa: E402
from models.client import Client  # noqa: E402
from models.empresa import Empresa  # noqa: E402
from models.user import User  # noqa: E402
from utils.tenant import get_tenant_scoped  # noqa: E402


NON_TENANT_ALLOWLIST = {
    "Empresa",
    "User",
    "Category",
    "EmailTemplate",
    "Assinatura",
    "Invitation",
    "LimiteContratado",
    "PasswordResetToken",
    "PlatformAsaasWebhookEvent",
    "RegulatoryTariffImport",
    "RegulatoryTariffPreview",
    "RegulatoryTariff",
}
PRODUCTION_ROOT = Path(__file__).resolve().parents[2]


def _model_registry():
    return {
        cls.__name__: cls
        for cls in db.Model.registry._class_registry.values()
        if isinstance(cls, type) and hasattr(cls, "__tablename__")
    }


def _is_tenant_model(model_name):
    model = _model_registry().get(model_name)
    return model is not None and issubclass(model, TenantMixin)


def _direct_model_name(node, imported_models):
    if isinstance(node, ast.Name) and node.id in imported_models:
        return imported_models[node.id]
    return None


def _scan_source(source, filename="<snippet>"):
    tree = ast.parse(source, filename=filename)
    imported_models = {}
    violations = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("models."):
            for alias in node.names:
                imported_models[alias.asname or alias.name] = alias.name

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        func = node.func
        model_name = None
        reason = None

        if (
            isinstance(func, ast.Attribute)
            and func.attr in {"get", "get_or_404"}
            and isinstance(func.value, ast.Attribute)
            and func.value.attr == "query"
        ):
            model_name = _direct_model_name(func.value.value, imported_models)
            reason = f".{func.attr}()"
        elif isinstance(func, ast.Attribute) and func.attr == "get":
            receiver = func.value
            is_session = isinstance(receiver, ast.Name) and receiver.id == "session"
            is_db_session = (
                isinstance(receiver, ast.Attribute)
                and receiver.attr == "session"
                and isinstance(receiver.value, ast.Name)
                and receiver.value.id == "db"
            )
            if is_session or is_db_session:
                entity = node.args[0] if node.args else None
                if entity is None:
                    for keyword in node.keywords:
                        if keyword.arg in {"entity", "model"}:
                            entity = keyword.value
                            break
                model_name = _direct_model_name(entity, imported_models)
                reason = "Session.get()"

        if model_name and _is_tenant_model(model_name):
            violations.append((node.lineno, model_name, reason))
        elif reason and isinstance(func, ast.Attribute):
            likely_model_lookup = (
                (func.attr in {"get", "get_or_404"} and isinstance(func.value, ast.Attribute) and func.value.attr == "query")
                or (
                    func.attr == "get"
                    and (
                        isinstance(func.value, ast.Name)
                        and func.value.id == "session"
                        or isinstance(func.value, ast.Attribute)
                        and func.value.attr == "session"
                        and isinstance(func.value.value, ast.Name)
                        and func.value.value.id == "db"
                    )
                )
            )
            if likely_model_lookup and model_name is None:
                violations.append((node.lineno, "<unresolved>", f"{reason}; revisar alvo de modelo"))

    return violations


def _scan_production():
    violations = []
    for path in PRODUCTION_ROOT.rglob("*.py"):
        if {"tests", "__pycache__", "venv"}.intersection(path.parts):
            continue
        violations.extend((path, *item) for item in _scan_source(path.read_text(encoding="utf-8"), str(path)))
    return violations


class TenantScopedLookupTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Flask(__name__)
        cls.app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
        cls.app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        db.init_app(cls.app)
        with cls.app.app_context():
            db.create_all()
            db.session.add_all([
                Empresa(id=7, nome="Tenant 7", slug="tenant-7"),
                Empresa(id=8, nome="Tenant 8", slug="tenant-8"),
                Client(id=1, empresa_id=7, nome="Client 1", cpf="12345678901", email="client1@example.test"),
            ])
            db.session.commit()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()

    def test_helper_returns_none_without_tenant_context(self):
        with self.app.test_request_context("/"):
            self.assertIsNone(get_tenant_scoped(Client, 1))

    def test_helper_scopes_lookup_to_current_tenant(self):
        with self.app.test_request_context("/"):
            g.current_empresa_id = 7
            self.assertEqual(get_tenant_scoped(Client, 1).empresa_id, 7)
            g.current_empresa_id = 8
            self.assertIsNone(get_tenant_scoped(Client, 1))

    def test_production_has_no_unscoped_tenant_primary_key_lookup(self):
        violations = _scan_production()
        self.assertEqual([], violations, "Unscoped tenant lookup(s): %s" % violations)

    def test_alias_of_tenant_model_is_detected(self):
        source = "from models.client import Client as Alias\nitem = Alias.query.get(1)"
        self.assertEqual([(2, "Client", ".get()")], _scan_source(source))

    def test_get_or_404_of_tenant_model_is_detected(self):
        source = "from models.client import Client\nitem = Client.query.get_or_404(1)"
        self.assertEqual([(2, "Client", ".get_or_404()")], _scan_source(source))

    def test_model_passed_by_variable_is_unresolvable_and_fails_review(self):
        source = "from models.client import Client\nmodel = Client\nitem = db.session.get(model, 1)"
        violations = _scan_source(source)
        self.assertEqual("<unresolved>", violations[0][1])
        self.assertIn("revisar alvo de modelo", violations[0][2])

    def test_session_get_keyword_entity_is_detected(self):
        source = "from models.client import Client\nitem = db.session.get(entity=Client, ident=1)"
        self.assertEqual([(2, "Client", "Session.get()")], _scan_source(source))

    def test_explicit_non_tenant_allowlist_is_not_tenant(self):
        registry = _model_registry()
        self.assertTrue(NON_TENANT_ALLOWLIST.issubset(registry))
        self.assertTrue(all(not issubclass(registry[name], TenantMixin) for name in NON_TENANT_ALLOWLIST))


if __name__ == "__main__":
    unittest.main()
