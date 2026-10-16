import unittest


class TestPermissionService(unittest.TestCase):
    def test_reports_read_granted_to_owner_admin_financial_not_operator_or_viewer(self):
        from services.permission_service import can
        from types import SimpleNamespace

        for role in ('owner', 'admin', 'financial'):
            user = SimpleNamespace(role=role, is_platform_admin=False)
            self.assertTrue(can(user, 'reports.read'), f'{role} deveria ter reports.read')

        for role in ('operator', 'viewer'):
            user = SimpleNamespace(role=role, is_platform_admin=False)
            self.assertFalse(can(user, 'reports.read'), f'{role} nao deveria ter reports.read')


if __name__ == '__main__':
    unittest.main()
