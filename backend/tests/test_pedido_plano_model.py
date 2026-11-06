"""PedidoPlano: checkout pendente de pagamento da assinatura de plano."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402
from config import Config  # noqa: E402
from extensions import db  # noqa: E402
from models.pedido_plano import PedidoPlano  # noqa: E402
try:
    from .support import IsolatedTestRuntime  # noqa: E402
except ImportError:
    from support import IsolatedTestRuntime  # noqa: E402


class PedidoPlanoModelTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepare_test_runtime('sqlite://', 'pedido-plano-model-test')
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
        self.addCleanup(db.drop_all)

    def test_cria_pedido_pendente(self):
        pedido = PedidoPlano(email='a@b.com', plano_chave='starter', external_reference='hub-platform-pedido-x')
        db.session.add(pedido)
        db.session.commit()

        self.assertEqual(pedido.status, 'pendente')
        self.assertIsNone(pedido.token_hash)


if __name__ == '__main__':
    unittest.main()
