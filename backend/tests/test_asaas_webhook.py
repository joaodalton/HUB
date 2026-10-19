"""B2: HTTP authentication and real transactional/concurrent SQLite writes; no network."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cryptography.fernet import Fernet
from flask import g
from sqlalchemy.exc import OperationalError
from app import create_app
from config import Config
from extensions import db
from models.api_credential import ApiCredential
from models.client import Client
from models.consumer_unit import ConsumerUnit
from models.empresa import Empresa
from models.fatura import Fatura
from models.payment_webhook_event import PaymentWebhookEvent
from services import asaas_webhook_service as service
from services.asaas_client import AsaasClient, AsaasError
try:
    from .support import IsolatedTestRuntime
except ImportError:
    from support import IsolatedTestRuntime


class AsaasWebhookTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.prepare_test_runtime(f'sqlite:///{Path(cls.folder.name).as_posix()}/webhook.db',
            'webhook-tests', encryption_key=Fernet.generate_key().decode(), limiter_enabled=False)
        Config.ASAAS_API_BASE_URL = 'https://api-sandbox.asaas.com/v3'
        cls.app = create_app()
        cls.app.config['TESTING'] = True

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()
        cls.folder.cleanup()
        cls.restore_test_runtime()

    def setUp(self):
        with self.app.app_context():
            db.drop_all()
            db.create_all()
            for tenant in (1, 2):
                db.session.add(Empresa(id=tenant, nome=str(tenant), slug=f'webhook-{tenant}'))
                db.session.flush()
                client = Client(empresa_id=tenant, nome='Teste', cpf=f'{tenant:011}', email=f'{tenant}@test.local')
                db.session.add(client)
                db.session.flush()
                uc = ConsumerUnit(empresa_id=tenant, client_id=client.id, codigo=f'UC-{tenant}')
                db.session.add(uc)
                db.session.flush()
                db.session.add(Fatura(id=tenant, empresa_id=tenant, client_id=client.id,
                    consumer_unit_id=uc.id, concessionaria='Copel', competencia='2026-09',
                    valor=Decimal('10'), mes_vencimento=date(2026, 9, 1), asaas_id=f'pay_{tenant}',
                    external_reference=f'hub-{tenant}', status_interno='emitida',
                    updated_at=datetime(2026, 9, 1)))
                for env in ('sandbox', 'producao'):
                    credential = ApiCredential(empresa_id=tenant, provider='asaas', nome=f'webhook_token_{env}')
                    credential.set_segredo(f'token-{tenant}-{env}')
                    db.session.add(credential)
            db.session.commit()
        self.network = patch('requests.sessions.Session.request', side_effect=AssertionError('network forbidden'))
        self.network.start()
        self.addCleanup(self.network.stop)

    def payload(self, tenant=1, event_id='evt_hash&123', **payment):
        return {'id': event_id, 'event': 'PAYMENT_RECEIVED', 'dateCreated': '2026-09-14 12:00:00',
                'payment': {'id': f'pay_{tenant}', 'externalReference': f'hub-{tenant}',
                            'status': 'RECEIVED', **payment}}

    def post(self, payload=None, token='token-1-sandbox'):
        return self.app.test_client().post('/api/v1/webhooks/asaas',
            json=self.payload() if payload is None else payload, headers={'asaas-access-token': token})

    def snapshot(self):
        with self.app.app_context():
            return [(f.asaas_status, f.updated_at, f.status_interno, f.asaas_id)
                    for f in Fatura.query.order_by(Fatura.id).all()], PaymentWebhookEvent.query.count()

    def test_valid_event_updates_only_owner_and_records_minimal_audit(self):
        with patch.object(service.secrets, 'compare_digest', wraps=service.secrets.compare_digest) as compare:
            self.assertEqual(self.post().status_code, 200)
            compare.assert_called_once()
        rows, count = self.snapshot()
        self.assertEqual([r[0] for r in rows], ['received', 'pending'])
        self.assertEqual(count, 1)
        with self.app.app_context():
            record = PaymentWebhookEvent.query.one()
            self.assertEqual((record.empresa_id, record.fatura_id), (1, 1))
            self.assertIsNotNone(record.processed_at)
            self.assertEqual(len(record.payload_hash), 64)
            self.assertNotIn('payload', record.__table__.columns)

    def test_invalid_and_other_company_tokens_do_not_mutate_or_record(self):
        original = self.snapshot()
        for tenant, token in ((1, 'wrong'), (1, 'token-2-sandbox'), (2, 'token-1-sandbox'), (1, '')):
            self.assertEqual(self.post(self.payload(tenant), token).status_code, 401)
            self.assertEqual(self.snapshot(), original)

    def test_sequential_duplicate_does_not_update_timestamp_or_repeat_effect(self):
        with patch.object(service, '_aplicar', wraps=service._aplicar) as apply:
            self.assertEqual(self.post().status_code, 200)
            original = self.snapshot()
            self.assertEqual(self.post().status_code, 200)
            self.assertEqual(self.snapshot(), original)
            apply.assert_called_once()

    def test_concurrent_duplicate_is_serialized_by_database(self):
        barrier = threading.Barrier(2)
        resolver = service._resolver_e_autenticar
        def resolve(*args):
            result = resolver(*args)
            barrier.wait(timeout=10)
            return result
        with patch.object(service, '_resolver_e_autenticar', side_effect=resolve), \
                patch.object(service, '_aplicar', wraps=service._aplicar) as apply, \
                ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(self.post) for _ in range(2)]
            self.assertEqual([f.result(timeout=20).status_code for f in futures], [200, 200])
            apply.assert_called_once()
        self.assertEqual(self.snapshot()[1], 1)

    def test_reference_resolves_pending_b1_without_changing_emission_reservation(self):
        with self.app.app_context():
            fatura = db.session.get(Fatura, 1)
            fatura.asaas_id = None
            fatura.status_interno = 'aguardando_emissao'
            fatura.emissao_iniciada_em = datetime(2026, 9, 1)
            db.session.commit()
        self.assertEqual(self.post().status_code, 200)
        rows, _ = self.snapshot()
        self.assertEqual(rows[0][2:], ('aguardando_emissao', None))
        with self.app.app_context():
            self.assertEqual(db.session.get(Fatura, 1).emissao_iniciada_em, datetime(2026, 9, 1))

    def test_legacy_safe_id_fallback(self):
        with self.app.app_context():
            fatura = db.session.get(Fatura, 1)
            fatura.external_reference = None
            fatura.status_interno = None
            db.session.commit()
        self.assertEqual(self.post(self.payload(externalReference='old-mutable-ref')).status_code, 200)
        self.assertIsNone(self.snapshot()[0][0][2])

    def test_ambiguous_id_rejected_but_unique_reference_resolves(self):
        with self.app.app_context():
            db.session.get(Fatura, 2).asaas_id = 'pay_1'
            db.session.commit()
        original = self.snapshot()
        self.assertEqual(self.post(self.payload(externalReference=None)).status_code, 401)
        self.assertEqual(self.snapshot(), original)
        self.assertEqual(self.post().status_code, 200)

    def test_unknown_and_conflicting_identifiers_share_generic_error(self):
        bodies = []
        for payment in ({'id': 'pay_missing', 'externalReference': None},
                        {'id': 'pay_2'}, {'externalReference': 'hub-2'}):
            response = self.post(self.payload(**payment))
            self.assertEqual(response.status_code, 401)
            bodies.append(response.json)
        self.assertEqual(bodies, [bodies[0]] * 3)
        self.assertEqual(self.snapshot()[1], 0)

    def test_invalid_payload_is_controlled(self):
        for payload in ([], {}, {'payment': []}, {'payment': {'id': 'pay_1'}},
                        self.payload(id=[]), self.payload(externalReference={})):
            self.assertEqual(self.post(payload).status_code, 400)
        self.assertEqual(self.snapshot()[1], 0)

    def test_failure_after_fatura_update_rolls_back_event_and_fatura(self):
        original = self.snapshot()
        apply = service._aplicar
        def fail(*args):
            apply(*args)
            raise OperationalError('simulated', {}, Exception('database unavailable'))
        with patch.object(service, '_aplicar', side_effect=fail):
            self.assertEqual(self.post().status_code, 503)
        self.assertEqual(self.snapshot(), original)
        self.assertEqual(self.post().status_code, 200)

    def test_commit_failure_rolls_back_both_and_allows_redelivery(self):
        original = self.snapshot()
        with patch.object(db.session, 'commit', side_effect=OperationalError('simulated', {}, Exception())):
            self.assertEqual(self.post().status_code, 503)
        self.assertEqual(self.snapshot(), original)
        self.assertEqual(self.post().status_code, 200)

    def test_event_id_cannot_be_reused_for_other_tenant(self):
        self.assertEqual(self.post().status_code, 200)
        original = self.snapshot()
        self.assertEqual(self.post(self.payload(2), 'token-2-sandbox').status_code, 409)
        self.assertEqual(self.snapshot(), original)

    def test_tenant_context_restored_and_ledger_filtered(self):
        with self.app.test_request_context('/'):
            g.current_empresa_id = 2
            service.processar_webhook(self.payload(), 'token-1-sandbox')
            self.assertEqual(g.current_empresa_id, 2)
            self.assertEqual(PaymentWebhookEvent.query.count(), 0)
            g.current_empresa_id = 1
            self.assertEqual(PaymentWebhookEvent.query.count(), 1)

    def test_environment_and_missing_token_fail_closed_without_global_fallback(self):
        with patch.object(Config, 'ASAAS_API_BASE_URL', 'https://api.asaas.com/v3'):
            self.assertEqual(self.post().status_code, 401)
            self.assertEqual(self.post(token='token-1-producao').status_code, 200)
        with self.app.app_context():
            ApiCredential.query.filter_by(empresa_id=1).delete()
            db.session.commit()
        with patch.object(Config, 'ASAAS_WEBHOOK_TOKEN', 'global'):
            self.assertEqual(self.post(token='global').status_code, 401)
        with patch.object(Config, 'ASAAS_API_BASE_URL', 'https://unknown.test/v3'):
            self.assertEqual(self.post().status_code, 401)

    def test_unsupported_status_does_not_default_to_pending(self):
        self.assertEqual(self.post(self.payload(status='NEW_STATUS')).status_code, 422)
        self.assertEqual(self.snapshot()[1], 0)

    def test_unknown_event_and_invalid_fields_roll_back(self):
        original = self.snapshot()
        payload = self.payload()
        payload['event'] = 'PAYMENT_UNKNOWN'
        self.assertEqual(self.post(payload).status_code, 422)
        self.assertEqual(self.post(self.payload(bankSlipUrl=[])).status_code, 400)
        self.assertEqual(self.snapshot(), original)

    def test_secret_decryption_failure_is_generic_and_no_global_fallback(self):
        with self.app.app_context():
            ApiCredential.query.filter_by(empresa_id=1, nome='webhook_token_sandbox').one().segredo_encrypted = 'bad-cipher'
            db.session.commit()
        response = self.post()
        self.assertEqual(response.status_code, 401)
        self.assertNotIn('bad-cipher', response.get_data(as_text=True))
        self.assertEqual(self.snapshot()[1], 0)

    def test_remote_urls_update_only_when_present_and_duplicate_does_not_reapply(self):
        self.assertEqual(self.post(self.payload(bankSlipUrl='https://example.test/boleto')).status_code, 200)
        self.assertEqual(self.post(self.payload(event_id='evt_next')).status_code, 200)
        self.assertEqual(self.post(self.payload(bankSlipUrl='https://example.test/changed')).status_code, 200)
        with self.app.app_context():
            self.assertEqual(db.session.get(Fatura, 1).boleto_url, 'https://example.test/boleto')

    def test_deleted_event_is_not_bank_slip_cancellation(self):
        payload = self.payload(status='PENDING')
        payload['event'] = 'PAYMENT_BANK_SLIP_CANCELLED'
        self.assertEqual(self.post(payload).status_code, 200)
        self.assertEqual(self.snapshot()[0][0][0], 'pending')
        payload.update(id='evt_delete', event='PAYMENT_DELETED')
        self.assertEqual(self.post(payload).status_code, 200)
        self.assertEqual(self.snapshot()[0][0][0], 'canceled')

    def test_api_selection_never_uses_webhook_token_or_other_environment(self):
        with self.app.app_context():
            with self.assertRaises(AsaasError):
                AsaasClient(1)
            other = ApiCredential(empresa_id=1, provider='asaas', nome='api_key_producao')
            other.set_segredo('production-key')
            db.session.add(other)
            db.session.commit()
            with self.assertRaises(AsaasError):
                AsaasClient(1)
            credential = ApiCredential(empresa_id=1, provider='asaas', nome='Principal')
            credential.set_segredo('legacy-key')
            db.session.add(credential)
            db.session.commit()
            self.assertEqual(AsaasClient(1)._headers['access_token'], 'legacy-key')
            credential = ApiCredential(empresa_id=1, provider='asaas', nome='api_key_sandbox')
            credential.set_segredo('sandbox-key')
            db.session.add(credential)
            db.session.commit()
            self.assertEqual(AsaasClient(1)._headers['access_token'], 'sandbox-key')


if __name__ == '__main__':
    unittest.main()
