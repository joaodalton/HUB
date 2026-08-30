"""Regressoes estaticas para os controles de seguranca estruturais do HUB."""
from pathlib import Path
import unittest


BACKEND = Path(__file__).resolve().parent


class SecurityStructureTests(unittest.TestCase):
    def _source(self, relative_path: str) -> str:
        return (BACKEND / relative_path).read_text(encoding='utf-8')

    def test_tenant_models_use_mixin(self):
        expected = {
            'models/setting.py': 'class Setting(TenantMixin, db.Model):',
            'models/log_entry.py': 'class LogEntry(TenantMixin, db.Model):',
            'models/rateio_historico.py': 'class RateioHistorico(TenantMixin, db.Model):',
        }
        for path, declaration in expected.items():
            with self.subTest(path=path):
                self.assertIn(declaration, self._source(path))

    def test_drive_cache_is_tenant_keyed(self):
        source = self._source('services/drive_service.py')
        self.assertIn('_drive_service_cache: dict[int, GoogleDriveService]', source)
        self.assertIn('_drive_service_cache[empresa_id]', source)
        self.assertIn("self.root_folder_id not in metadata.get('parents', [])", source)

    def test_session_tokens_are_revocable(self):
        auth_source = self._source('utils/auth.py')
        self.assertIn("'session_version': user.session_version", auth_source)
        self.assertIn('user.session_version == token_data.get', auth_source)
        self.assertIn('session_version = db.Column', self._source('models/user.py'))

    def test_sensitive_configuration_requires_platform_admin(self):
        self.assertEqual(
            self._source('routes/config_routes.py').count('@require_platform_admin()'),
            5,
        )

    def test_business_routes_apply_rbac(self):
        route_permissions = {
            'routes/client_routes.py': 5,
            'routes/plant_routes.py': 6,
            'routes/uc_routes.py': 5,
            'routes/document_routes.py': 7,
            'routes/rateio_routes.py': 10,
        }
        for path, minimum in route_permissions.items():
            with self.subTest(path=path):
                self.assertGreaterEqual(self._source(path).count('@require_permission('), minimum)


if __name__ == '__main__':
    unittest.main()
