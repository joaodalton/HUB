"""ARCH-PLATFORM-1: platform credentials and webhook never enter tenant billing."""
from concurrent.futures import ThreadPoolExecutor
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import Config
from extensions import db
from models.fatura import Fatura
from models.payment_webhook_event import PaymentWebhookEvent
from hub_platform.models.platform_asaas_webhook_event import PlatformAsaasWebhookEvent
from models.api_credential import ApiCredential
from models.pedido_plano import PedidoPlano
from sqlalchemy.exc import OperationalError
from services.asaas_client import AsaasClient, PlatformAsaasService, AsaasError
try:
    from .test_asaas_webhook import AsaasWebhookTest
except ImportError:
    from test_asaas_webhook import AsaasWebhookTest


class PlatformAsaasBoundaryTest(AsaasWebhookTest):
    def platform_post(self, payload=None, token='platform-token'):
        return self.app.test_client().post('/api/v1/webhooks/asaas/platform',
            json=self.payload(externalReference='hub-platform-test') if payload is None else payload,
            headers={'asaas-access-token': token})

    def test_platform_auth_and_ledger_are_separate_from_two_tenants(self):
        with patch.object(Config, 'PLATFORM_ASAAS_WEBHOOK_TOKEN', 'platform-token'):
            original = self.snapshot()
            for token in ('', 'token-1-sandbox', 'token-2-sandbox'):
                self.assertEqual(self.platform_post(token=token).status_code, 401)
            self.assertEqual(self.snapshot(), original)
            self.assertEqual(self.platform_post().status_code, 200)
            self.assertEqual(self.platform_post().status_code, 200)
            self.assertEqual(self.snapshot(), original)
            with self.app.app_context():
                self.assertEqual(PlatformAsaasWebhookEvent.query.count(), 1)
                self.assertEqual(PaymentWebhookEvent.query.count(), 0)
            self.assertEqual(self.post().status_code, 200)
            with self.app.app_context():
                self.assertEqual(PlatformAsaasWebhookEvent.query.count(), 1)
                self.assertEqual(PaymentWebhookEvent.query.count(), 1)
                self.assertEqual(Fatura.query.filter_by(asaas_status='received').count(), 1)

    def test_platform_event_collision_and_failed_write(self):
        with patch.object(Config, 'PLATFORM_ASAAS_WEBHOOK_TOKEN', 'platform-token'):
            self.assertEqual(self.platform_post(self.payload(externalReference='hub-1')).status_code, 422)
            self.assertEqual(self.platform_post().status_code, 200)
            self.assertEqual(self.platform_post(self.payload(tenant=2, externalReference='hub-platform-test')).status_code, 409)
            with self.app.app_context():
                self.assertEqual(PlatformAsaasWebhookEvent.query.count(), 1)

    def test_platform_commit_failure_rolls_back_and_redelivery_succeeds(self):
        with patch.object(Config, 'PLATFORM_ASAAS_WEBHOOK_TOKEN', 'platform-token'):
            with patch.object(db.session, 'commit', side_effect=OperationalError('simulated', {}, Exception())):
                self.assertEqual(self.platform_post().status_code, 503)
            with self.app.app_context():
                self.assertEqual(PlatformAsaasWebhookEvent.query.count(), 0)
            self.assertEqual(self.platform_post().status_code, 200)

    def test_concurrent_platform_delivery_has_one_receipt(self):
        with patch.object(Config, 'PLATFORM_ASAAS_WEBHOOK_TOKEN', 'platform-token'):
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(lambda _: self.platform_post().status_code, range(2)))
            self.assertEqual(results, [200, 200])
            with self.app.app_context():
                self.assertEqual(PlatformAsaasWebhookEvent.query.count(), 1)

    def _criar_pedido_pendente(self, external_reference='hub-platform-pedido-abc123'):
        with self.app.app_context():
            pedido = PedidoPlano(email='cliente@test.local', plano_chave='starter',
                external_reference=external_reference)
            db.session.add(pedido)
            db.session.commit()
            return pedido.id

    def test_webhook_payment_confirmed_gera_token_uma_vez(self):
        with patch.object(Config, 'PLATFORM_ASAAS_WEBHOOK_TOKEN', 'platform-token'):
            pedido_id = self._criar_pedido_pendente()
            payload = {'id': 'evt_pedido_1', 'event': 'PAYMENT_CONFIRMED',
                'payment': {'id': 'pay_pedido_1', 'externalReference': 'hub-platform-pedido-abc123'}}

            with patch('services.pedido_plano_service.send_email') as mock_send:
                self.assertEqual(self.platform_post(payload).status_code, 200)
                with self.app.app_context():
                    pedido = db.session.get(PedidoPlano, pedido_id)
                    self.assertEqual(pedido.status, 'pago')
                    self.assertIsNotNone(pedido.token_hash)
                    primeiro_hash = pedido.token_hash
                mock_send.assert_called_once()

                # Replay do mesmo evento (Asaas reenvia): nao gera segundo token nem e-mail.
                payload['id'] = 'evt_pedido_2'
                self.assertEqual(self.platform_post(payload).status_code, 200)
                with self.app.app_context():
                    self.assertEqual(db.session.get(PedidoPlano, pedido_id).token_hash, primeiro_hash)
                mock_send.assert_called_once()

    def test_webhook_payment_received_tambem_gera_token(self):
        # PIX/boleto tipicamente disparam PAYMENT_RECEIVED, nao PAYMENT_CONFIRMED
        # (majoritariamente de cartao) -- o checkout promete boleto/pix/cartao,
        # entao os dois eventos tem que confirmar o pagamento.
        with patch.object(Config, 'PLATFORM_ASAAS_WEBHOOK_TOKEN', 'platform-token'):
            pedido_id = self._criar_pedido_pendente(external_reference='hub-platform-pedido-pix1')
            payload = {'id': 'evt_pix_1', 'event': 'PAYMENT_RECEIVED',
                'payment': {'id': 'pay_pix_1', 'externalReference': 'hub-platform-pedido-pix1'}}

            with patch('services.pedido_plano_service.send_email', return_value=True):
                self.assertEqual(self.platform_post(payload).status_code, 200)
                with self.app.app_context():
                    pedido = db.session.get(PedidoPlano, pedido_id)
                    self.assertEqual(pedido.status, 'pago')
                    self.assertIsNotNone(pedido.token_hash)

    def test_webhook_redelivery_do_mesmo_evento_reprocessa_email_que_falhou(self):
        # ARCH-1 (finding critico #1): send_email falha na primeira entrega --
        # o pedido fica 'pendente' e a resposta tem que ser nao-2xx pra Asaas
        # redeliverar. A redelivery chega com o MESMO event_id (replay real,
        # nao um evento novo) -- isso bate no branch de dedupe (mesmo
        # payload_hash), que sem o fix retornaria 200 sem nunca chamar
        # confirmar_pagamento de novo, travando o cliente pra sempre.
        with patch.object(Config, 'PLATFORM_ASAAS_WEBHOOK_TOKEN', 'platform-token'):
            pedido_id = self._criar_pedido_pendente(external_reference='hub-platform-pedido-retry1')
            payload = {'id': 'evt_retry_1', 'event': 'PAYMENT_CONFIRMED',
                'payment': {'id': 'pay_retry_1', 'externalReference': 'hub-platform-pedido-retry1'}}

            with patch('services.pedido_plano_service.send_email', return_value=False):
                response = self.platform_post(dict(payload))
            self.assertEqual(response.status_code, 503)
            with self.app.app_context():
                pedido = db.session.get(PedidoPlano, pedido_id)
                self.assertEqual(pedido.status, 'pendente')
                self.assertIsNone(pedido.token_hash)

            # Redelivery da Asaas: mesmo event_id, mesmo payload exato.
            with patch('services.pedido_plano_service.send_email', return_value=True):
                response = self.platform_post(dict(payload))
            self.assertEqual(response.status_code, 200)
            with self.app.app_context():
                pedido = db.session.get(PedidoPlano, pedido_id)
                self.assertEqual(pedido.status, 'pago')
                self.assertIsNotNone(pedido.token_hash)

    def test_webhook_payment_confirmed_sem_pedido_correspondente_e_noop(self):
        with patch.object(Config, 'PLATFORM_ASAAS_WEBHOOK_TOKEN', 'platform-token'):
            payload = {'id': 'evt_pedido_sem_match', 'event': 'PAYMENT_CONFIRMED',
                'payment': {'id': 'pay_sem_match', 'externalReference': 'hub-platform-pedido-inexistente'}}
            self.assertEqual(self.platform_post(payload).status_code, 200)
            with self.app.app_context():
                self.assertIsNone(PedidoPlano.query.filter_by(
                    external_reference='hub-platform-pedido-inexistente').first())

    def test_platform_transport_uses_only_global_key_and_base_url(self):
        with self.app.app_context(), patch.object(Config, 'PLATFORM_ASAAS_API_KEY', 'platform-key'), \
                patch.object(Config, 'PLATFORM_ASAAS_API_BASE_URL', 'https://api-sandbox.asaas.com/v3'):
            for tenant in (1, 2):
                credential = ApiCredential(empresa_id=tenant, provider='asaas', nome='api_key_sandbox')
                credential.set_segredo(f'tenant-{tenant}-key')
                db.session.add(credential)
            db.session.commit()
            client = PlatformAsaasService()
            self.assertEqual(client._headers['access_token'], 'platform-key')
            self.assertEqual(client._base_url, 'https://api-sandbox.asaas.com/v3')
            self.assertEqual(AsaasClient(1)._headers['access_token'], 'tenant-1-key')
            self.assertEqual(AsaasClient(2)._headers['access_token'], 'tenant-2-key')
            response = Mock(ok=True)
            response.json.return_value = {'id': 'pay-test'}
            with patch('services.asaas_client.requests.request', return_value=response) as request:
                for gateway in (AsaasClient(1), AsaasClient(2), client):
                    self.assertEqual(gateway.criar_cobranca({'customer': 'test'})['id'], 'pay-test')
            self.assertEqual([call.kwargs['headers']['access_token'] for call in request.call_args_list],
                ['tenant-1-key', 'tenant-2-key', 'platform-key'])
            self.assertEqual([call.args[1] for call in request.call_args_list],
                ['https://api-sandbox.asaas.com/v3/payments'] * 3)
        with self.app.app_context(), patch.object(Config, 'PLATFORM_ASAAS_API_KEY', ''):
            with self.assertRaises(AsaasError):
                PlatformAsaasService()
        with self.app.app_context(), patch.object(Config, 'PLATFORM_ASAAS_API_KEY', 'platform-key'), \
                patch.object(Config, 'PLATFORM_ASAAS_API_BASE_URL', ''):
            with self.assertRaises(AsaasError):
                PlatformAsaasService()


if __name__ == '__main__':
    unittest.main()
