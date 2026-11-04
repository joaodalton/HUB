"""criar_pedido: valida plano comprável, abre assinatura ASAAS e grava PedidoPlano."""
import sys
import unittest
from datetime import datetime, timedelta
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
            criar_pedido('a@b.com', 'teste', {'billingType': 'PIX'})

    def test_rejeita_plano_inexistente(self):
        with self.assertRaises(ValueError):
            criar_pedido('a@b.com', 'inexistente', {'billingType': 'PIX'})

    def test_rejeita_billing_type_ausente(self):
        with self.assertRaises(ValueError):
            criar_pedido('a@b.com', 'starter', {'cpfCnpj': '12345678900'})

    def test_rejeita_billing_type_invalido(self):
        with self.assertRaises(ValueError):
            criar_pedido('a@b.com', 'starter', {'cpfCnpj': '12345678900', 'billingType': 'DINHEIRO'})

    def test_rejeita_email_muito_longo(self):
        email_longo = ('a' * 145) + '@b.com'
        with self.assertRaises(ValueError):
            criar_pedido(email_longo, 'starter', {'billingType': 'PIX'})

    def test_cria_pedido_com_external_reference_prefixo_hub_platform(self):
        with mock.patch('services.pedido_plano_service._asaas_transport') as mocked:
            mocked.return_value.criar_cliente.return_value = {'id': 'cus_1'}
            mocked.return_value.criar_assinatura.return_value = {'id': 'sub_1'}
            criar_pedido('a@b.com', 'starter', {'cpfCnpj': '12345678900', 'nome': 'Fulano', 'billingType': 'PIX'})
            cliente_payload = mocked.return_value.criar_cliente.call_args[0][0]
            assinatura_payload = mocked.return_value.criar_assinatura.call_args[0][0]
        self.assertNotIn('billingType', cliente_payload)
        self.assertEqual(assinatura_payload['billingType'], 'PIX')
        pedido = PedidoPlano.query.filter_by(email='a@b.com').first()
        self.assertTrue(pedido.external_reference.startswith('hub-platform-'))
        self.assertEqual(pedido.asaas_subscription_id, 'sub_1')
        self.assertEqual(pedido.asaas_customer_id, 'cus_1')
        self.assertEqual(pedido.status, 'pendente')

    def test_falha_asaas_nao_deixa_pedido_orfao(self):
        with mock.patch('services.pedido_plano_service._asaas_transport') as mocked:
            mocked.return_value.criar_cliente.side_effect = RuntimeError('ASAAS indisponivel')
            with self.assertRaises(RuntimeError):
                criar_pedido('c@d.com', 'starter', {'billingType': 'BOLETO'})
        self.assertIsNone(PedidoPlano.query.filter_by(email='c@d.com').first())

    def test_falha_construcao_transporte_nao_deixa_pedido_orfao(self):
        with mock.patch('services.pedido_plano_service._asaas_transport') as mocked:
            mocked.side_effect = RuntimeError('credenciais Asaas invalidas')
            with self.assertRaises(RuntimeError):
                criar_pedido('e@f.com', 'starter', {'billingType': 'BOLETO'})
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

    def test_confirmar_pagamento_e_no_op_se_outra_chamada_ja_esta_processando(self):
        # Simula a janela de corrida: outra chamada concorrente ja trocou
        # pendente->processando entre a leitura e o UPDATE condicional desta.
        pedido = PedidoPlano(email='k@l.com', plano_chave='starter', external_reference='hub-platform-ref-3', status='processando')
        db.session.add(pedido)
        db.session.commit()

        with mock.patch('services.pedido_plano_service.send_email') as mocked_send:
            resultado = confirmar_pagamento('hub-platform-ref-3')

        mocked_send.assert_not_called()
        self.assertTrue(resultado)
        db.session.refresh(pedido)
        self.assertEqual(pedido.status, 'processando')
        self.assertIsNone(pedido.token_hash)

    def test_confirmar_pagamento_retoma_processando_travado_por_timeout(self):
        # Pedido ficou presa em 'processando' porque o processo caiu entre o
        # UPDATE pendente->processando e o commit seguinte (deploy/OOM/etc).
        # Uma nova chamada (redelivery da Asaas) precisa destravar em vez de
        # virar no-op silencioso pra sempre.
        pedido = PedidoPlano(
            email='m@n.com',
            plano_chave='starter',
            external_reference='hub-platform-ref-4',
            status='processando',
            processando_desde=datetime.utcnow() - timedelta(minutes=5),
        )
        db.session.add(pedido)
        db.session.commit()

        with mock.patch('services.pedido_plano_service.send_email', return_value=True) as mocked_send:
            resultado = confirmar_pagamento('hub-platform-ref-4')

        mocked_send.assert_called_once()
        self.assertTrue(resultado)
        db.session.refresh(pedido)
        self.assertEqual(pedido.status, 'pago')
        self.assertIsNotNone(pedido.token_hash)


if __name__ == '__main__':
    unittest.main()
