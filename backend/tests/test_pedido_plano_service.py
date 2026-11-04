"""criar_pedido: valida plano comprável, abre assinatura ASAAS e grava PedidoPlano."""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402
from config import Config  # noqa: E402
from extensions import db  # noqa: E402
from models.pedido_plano import PedidoPlano  # noqa: E402
from services.pedido_plano_service import confirmar_pagamento, criar_pedido  # noqa: E402
try:
    from .support import IsolatedTestRuntime  # noqa: E402
except ImportError:
    from support import IsolatedTestRuntime  # noqa: E402


class PedidoPlanoServiceTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepare_test_runtime('sqlite://', 'pedido-plano-service-test')
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

    def test_rejeita_plano_nao_compravel(self):
        with self.assertRaises(ValueError):
            criar_pedido('a@b.com', 'teste', {})

    def test_rejeita_plano_inexistente(self):
        with self.assertRaises(ValueError):
            criar_pedido('a@b.com', 'inexistente', {})

    def test_cria_pedido_com_external_reference_prefixo_hub_platform(self):
        with mock.patch('services.pedido_plano_service._asaas_transport') as mocked:
            mocked.return_value.criar_cliente.return_value = {'id': 'cus_1'}
            mocked.return_value.criar_assinatura.return_value = {'id': 'sub_1'}
            criar_pedido('a@b.com', 'starter', {'cpfCnpj': '12345678900', 'nome': 'Fulano'})
        pedido = PedidoPlano.query.filter_by(email='a@b.com').first()
        self.assertTrue(pedido.external_reference.startswith('hub-platform-'))
        self.assertEqual(pedido.asaas_subscription_id, 'sub_1')
        self.assertEqual(pedido.asaas_customer_id, 'cus_1')
        self.assertEqual(pedido.status, 'pendente')

    def test_falha_asaas_nao_deixa_pedido_orfao(self):
        with mock.patch('services.pedido_plano_service._asaas_transport') as mocked:
            mocked.return_value.criar_cliente.side_effect = RuntimeError('ASAAS indisponivel')
            with self.assertRaises(RuntimeError):
                criar_pedido('c@d.com', 'starter', {})
        self.assertIsNone(PedidoPlano.query.filter_by(email='c@d.com').first())

    def test_falha_construcao_transporte_nao_deixa_pedido_orfao(self):
        with mock.patch('services.pedido_plano_service._asaas_transport') as mocked:
            mocked.side_effect = RuntimeError('credenciais Asaas invalidas')
            with self.assertRaises(RuntimeError):
                criar_pedido('e@f.com', 'starter', {})
        self.assertIsNone(PedidoPlano.query.filter_by(email='e@f.com').first())

    def test_confirmar_pagamento_marca_pago_quando_email_enviado(self):
        pedido = PedidoPlano(email='g@h.com', plano_chave='starter', external_reference='hub-platform-ref-1')
        db.session.add(pedido)
        db.session.commit()

        with mock.patch('services.pedido_plano_service.send_email', return_value=True):
            confirmar_pagamento('hub-platform-ref-1')

        db.session.refresh(pedido)
        self.assertEqual(pedido.status, 'pago')
        self.assertIsNotNone(pedido.token_hash)

    def test_confirmar_pagamento_mantem_pendente_quando_email_falha(self):
        pedido = PedidoPlano(email='i@j.com', plano_chave='starter', external_reference='hub-platform-ref-2')
        db.session.add(pedido)
        db.session.commit()

        with mock.patch('services.pedido_plano_service.send_email', return_value=False):
            confirmar_pagamento('hub-platform-ref-2')

        db.session.refresh(pedido)
        self.assertEqual(pedido.status, 'pendente')
        self.assertIsNone(pedido.token_hash)

        # Idempotency guard nao bloqueia um proximo webhook retry: o pedido
        # ainda esta 'pendente', entao uma segunda chamada processa normalmente.
        with mock.patch('services.pedido_plano_service.send_email', return_value=True):
            confirmar_pagamento('hub-platform-ref-2')
        db.session.refresh(pedido)
        self.assertEqual(pedido.status, 'pago')
        self.assertIsNotNone(pedido.token_hash)


if __name__ == '__main__':
    unittest.main()
