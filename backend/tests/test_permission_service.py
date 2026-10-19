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

    def test_can_grants_worker_only_read_actions(self):
        from services.permission_service import can
        from types import SimpleNamespace

        # role has no entry in ROLE_PERMISSIONS, so a pass here can only come
        # from the worker bypass itself, not a role-permission coincidence.
        worker = SimpleNamespace(role='no-such-role', is_platform_admin=False, is_platform_worker=True)
        self.assertTrue(can(worker, 'clients.read'))
        self.assertFalse(can(worker, 'clients.create'))

    def test_can_any_grants_worker_only_if_a_read_action_present(self):
        from services.permission_service import can_any
        from types import SimpleNamespace

        worker = SimpleNamespace(role='no-such-role', is_platform_admin=False, is_platform_worker=True)
        self.assertTrue(can_any(worker, ['clients.create', 'clients.read']))
        self.assertFalse(can_any(worker, ['clients.create', 'clients.update']))

    def test_is_platform_admin_bypass_unchanged_for_non_read_action(self):
        from services.permission_service import can, can_any
        from types import SimpleNamespace

        admin = SimpleNamespace(role='viewer', is_platform_admin=True, is_platform_worker=False)
        self.assertTrue(can(admin, 'clients.delete'))
        self.assertTrue(can_any(admin, ['clients.delete']))

    def test_require_role_worker_passes_safe_method_blocks_unsafe_method(self):
        from flask import Flask, g
        from services.permission_service import require_role
        from types import SimpleNamespace

        app = Flask(__name__)

        @require_role('owner')
        def view():
            return 'ok', 200

        worker = SimpleNamespace(role='viewer', is_platform_admin=False, is_platform_worker=True)

        with app.test_request_context('/', method='GET'):
            g.current_user = worker
            body, status = view()
            self.assertEqual(status, 200)

        with app.test_request_context('/', method='POST'):
            g.current_user = worker
            response, status = view()
            self.assertEqual(status, 403)

    def test_require_role_non_worker_still_blocked_regardless_of_method(self):
        from flask import Flask, g
        from services.permission_service import require_role
        from types import SimpleNamespace

        app = Flask(__name__)

        @require_role('owner')
        def view():
            return 'ok', 200

        viewer = SimpleNamespace(role='viewer', is_platform_admin=False, is_platform_worker=False)

        with app.test_request_context('/', method='GET'):
            g.current_user = viewer
            response, status = view()
            self.assertEqual(status, 403)

    def test_require_platform_access_allows_admin_or_worker_blocks_others(self):
        from flask import Flask, g
        from services.permission_service import require_platform_access
        from types import SimpleNamespace

        app = Flask(__name__)

        @require_platform_access()
        def view():
            return 'ok', 200

        admin = SimpleNamespace(role='viewer', is_platform_admin=True, is_platform_worker=False)
        worker = SimpleNamespace(role='viewer', is_platform_admin=False, is_platform_worker=True)
        tenant = SimpleNamespace(role='owner', is_platform_admin=False, is_platform_worker=False)

        with app.test_request_context('/'):
            g.current_user = admin
            body, status = view()
            self.assertEqual(status, 200)

        with app.test_request_context('/'):
            g.current_user = worker
            body, status = view()
            self.assertEqual(status, 200)

        with app.test_request_context('/'):
            g.current_user = tenant
            response, status = view()
            self.assertEqual(status, 403)


if __name__ == '__main__':
    unittest.main()
