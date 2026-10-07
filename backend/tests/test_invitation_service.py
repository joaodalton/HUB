"""Lifecycle regression coverage for service-level invitation revocation."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402
from config import Config  # noqa: E402
from extensions import db  # noqa: E402
from models.empresa import Empresa  # noqa: E402
from models.invitation import Invitation  # noqa: E402
from services.invitation_service import (  # noqa: E402
    criar_convite,
    revogar_convite,
    verificar_convite,
)
try:
    from .support import IsolatedTestRuntime  # noqa: E402
except ImportError:
    from support import IsolatedTestRuntime  # noqa: E402


class InvitationServiceTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepare_test_runtime('sqlite://', 'invitation-service-test')
        Config.FRONTEND_URL = 'https://hub.test'
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
        self.empresa = Empresa(nome='Convites', slug='convites-teste')
        db.session.add(self.empresa)
        db.session.commit()
        self.addCleanup(db.drop_all)

    def test_revoked_invitation_cannot_be_verified(self):
        convite, token = criar_convite(self.empresa.id, ' Pessoa@Exemplo.test ', 'viewer', None)

        self.assertEqual(convite['status'], 'pending')
        self.assertEqual(Invitation.query.get(convite['id']).status, 'pending')
        usable = verificar_convite(token)
        self.assertEqual(usable['email'], 'pessoa@exemplo.test')
        self.assertEqual(usable['role'], 'viewer')
        self.assertEqual(usable['empresaNome'], 'Convites')
        revoked = revogar_convite(convite['id'], self.empresa.id)

        self.assertEqual(revoked['status'], 'revoked')
        self.assertEqual(Invitation.query.get(convite['id']).status, 'revoked')
        with self.assertRaisesRegex(ValueError, 'revogado'):
            verificar_convite(token)


if __name__ == '__main__':
    unittest.main()
