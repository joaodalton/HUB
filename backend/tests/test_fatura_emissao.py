"""B1: real database transactions/concurrency, simulated ASAAS only."""
import os
import sys
import tempfile
import threading
import unittest
from datetime import date
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from flask import g
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError, OperationalError
from app import create_app
from config import Config
from extensions import db
from models.client import Client
from models.consumer_unit import ConsumerUnit
from models.empresa import Empresa
from models.fatura import Fatura
from models.user import User
from services import fatura_service as service
from services.asaas_client import AsaasError
from utils.auth import generate_token
try:
    from .support import IsolatedTestRuntime
except ImportError:
    from support import IsolatedTestRuntime


class FaturaEmissaoTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.uri = 'sqlite:///' + (Path(cls.temp.name) / 'b1.db').as_posix()
        cls.prepare_test_runtime(cls.uri, 'b1-test', limiter_enabled=False)
        Config.SENTRY_DSN = ''
        cls.app = create_app()
        cls.observer = create_engine(cls.uri)

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()
        cls.observer.dispose()
        cls.temp.cleanup()
        cls.restore_test_runtime()

    def setUp(self):
        with self.app.app_context():
            db.create_all()
            for tenant in (1, 2):
                db.session.add(Empresa(id=tenant, nome=str(tenant), slug=f'b1-{tenant}'))
                db.session.add(User(id=tenant, empresa_id=tenant, nome='Owner',
                    email=f'owner{tenant}@test.local', password_hash='x', role='owner'))
                db.session.add(Client(id=tenant, empresa_id=tenant, nome='Cliente',
                    cpf=f'{tenant:011d}', email=f'c{tenant}@test.local', concessionaria='Copel',
                    asaas_customer_id=f'cus_{tenant}'))
                db.session.add(ConsumerUnit(id=tenant, empresa_id=tenant, client_id=tenant,
                    codigo=f'uc{tenant}', concessionaria='Copel'))
            db.session.commit()
        self.remote = {}
        self.post_count = 0
        self.lookup_count = 0
        self.guard = threading.Lock()
        self.client_patch = patch.object(service, 'AsaasClient')
        self.asaas = self.client_patch.start().return_value
        self.addCleanup(self.client_patch.stop)
        self.asaas.criar_cobranca.side_effect = self._post
        self.asaas.consultar_por_referencia.side_effect = self._lookup

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _rows(self):
        with self.observer.connect() as connection:
            return connection.execute(text('SELECT * FROM faturas')).mappings().all()

    def _post(self, payload):
        # Another connection must see the committed intention before the external effect.
        row = next(r for r in self._rows() if r['external_reference'] == payload['externalReference'])
        self.assertIsNone(row['asaas_id'])
        self.assertEqual(row['status_interno'], 'aguardando_emissao')
        self.assertIsNotNone(row['emissao_iniciada_em'])
        self.assertEqual(row['payment_customer_id'], payload['customer'])
        with self.guard:
            self.post_count += 1
            payment = {**payload, 'id': f'pay_{self.post_count}', 'status': 'PENDING',
                       'bankSlipUrl': 'https://example.test/boleto'}
            self.remote[payload['externalReference']] = payment
        return payment

    def _lookup(self, reference):
        with self.guard:
            self.lookup_count += 1
            return self.remote.get(reference)

    def _emit(self, tenant=1, **overrides):
        command = dict(clienteId=tenant, ucId=tenant, valor='10.00',
                       competencia='2026-09', mesVencimento='2026-10-05')
        command.update(overrides)
        with self.app.test_request_context('/'):
            g.current_empresa_id = tenant
            return service.emitir(command, tenant, tenant)

    def test_normal_and_normalized_sequential_retry(self):
        first = self._emit()
        again = self._emit(valor=10)
        self.assertEqual(first['id'], again['id'])
        self.assertEqual(first['statusInterno'], 'emitida')
        self.assertEqual(first['asaasId'], 'pay_1')
        self.assertEqual(len(self._rows()), 1)
        self.assertEqual(self.post_count, 1)

    def test_canceled_command_does_not_create_an_implicit_new_version(self):
        first = self._emit()
        self.asaas.cancelar_cobranca.return_value = {'id': first['asaasId'], 'deleted': True}
        with self.app.test_request_context('/'):
            g.current_empresa_id = 1
            canceled = service.cancelar(service.obter(first['id'], 1))
        self.assertEqual(canceled['statusInterno'], 'cancelada')
        self.assertEqual(canceled['asaasStatus'], 'canceled')
        self.assertEqual(self._emit()['id'], first['id'])
        self.assertEqual(self.post_count, 1)

    def test_concurrent_insert_and_claim_have_one_winner(self):
        barrier = threading.Barrier(2)
        original_commit = db.session.commit

        def commit():
            if any(isinstance(obj, Fatura) for obj in db.session.new):
                barrier.wait(timeout=10)
            return original_commit()

        def emit():
            try:
                return self._emit()
            except service.EmissaoPendente:
                return None

        with patch.object(db.session, 'commit', side_effect=commit):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: emit(), range(2)))
        self.assertTrue(any(results))
        self.assertEqual(self.post_count, 1)
        self.assertEqual(len(self._rows()), 1)
        self.assertEqual(self._emit()['asaasId'], 'pay_1')

    def test_inflight_request_cannot_be_reissued(self):
        entered, release = threading.Event(), threading.Event()

        def post(payload):
            entered.set()
            self.assertTrue(release.wait(10))
            return self._post(payload)

        self.asaas.criar_cobranca.side_effect = post
        with ThreadPoolExecutor(max_workers=1) as pool:
            first = pool.submit(self._emit)
            try:
                self.assertTrue(entered.wait(10))
                with self.assertRaises(service.EmissaoPendente):
                    self._emit()
            finally:
                release.set()
            self.assertEqual(first.result(timeout=10)['asaasId'], 'pay_1')
        self.assertEqual(self.post_count, 1)

    def test_failure_before_customer_never_claims_success(self):
        with self.app.app_context():
            Client.query.filter_by(id=1).update({'asaas_customer_id': None})
            db.session.commit()
        self.asaas.criar_cliente.side_effect = AsaasError('customer rejected')
        with self.assertRaises(AsaasError):
            self._emit()
        row = self._rows()[0]
        self.assertEqual(row['status_interno'], 'erro_emissao')
        self.assertIsNone(row['emissao_iniciada_em'])
        self.assertIsNone(row['asaas_id'])
        self.asaas.criar_cobranca.assert_not_called()
        self.asaas.criar_cliente.side_effect = None
        self.asaas.criar_cliente.return_value = {'id': 'cus_1'}
        self.assertEqual(self._emit()['id'], row['id'])

    def test_payment_rejection_or_timeout_never_blindly_reposts(self):
        self.asaas.criar_cobranca.side_effect = AsaasError('unknown outcome')
        for _ in range(2):
            with self.assertRaises(service.EmissaoPendente):
                self._emit()
        self.asaas.criar_cobranca.assert_called_once()
        self.assertEqual(self.lookup_count, 2)
        self.assertIsNone(self._rows()[0]['asaas_id'])

    def test_remote_success_then_timeout_reconciles(self):
        def post(payload):
            self._post(payload)
            raise AsaasError('response lost')
        self.asaas.criar_cobranca.side_effect = post
        self.assertEqual(self._emit()['asaasId'], 'pay_1')
        self.assertEqual(self._emit()['asaasId'], 'pay_1')
        self.assertEqual(self.post_count, 1)
        self.assertEqual(self.lookup_count, 1)

    def test_final_commit_failure_preserves_reference_and_retry_recovers(self):
        original_commit = db.session.commit

        def commit():
            if any(isinstance(obj, Fatura) and obj.asaas_id for obj in db.session.dirty):
                raise OperationalError('commit', {}, RuntimeError('simulated disconnect'))
            return original_commit()

        with patch.object(db.session, 'commit', side_effect=commit):
            with self.assertRaises(service.EmissaoPendente):
                self._emit()
        row = self._rows()[0]
        self.assertIsNone(row['asaas_id'])
        self.assertIn(row['external_reference'], self.remote)
        self.assertEqual(self._emit()['id'], row['id'])
        self.assertEqual(self.post_count, 1)
        self.assertEqual(self.lookup_count, 1)

    def test_first_commit_failure_has_no_external_effect(self):
        with patch.object(db.session, 'commit', side_effect=OperationalError('commit', {}, Exception())):
            with self.assertRaises(OperationalError):
                self._emit()
        self.assertEqual(self._rows(), [])
        self.asaas.criar_cobranca.assert_not_called()
        self.asaas.criar_cliente.assert_not_called()

    def test_wrong_remote_payload_is_not_attached(self):
        def post(payload):
            payment = self._post(payload)
            payment['customer'] = 'foreign'
            return payment
        self.asaas.criar_cobranca.side_effect = post
        with self.assertRaises(AsaasError):
            self._emit()
        self.assertIsNone(self._rows()[0]['asaas_id'])
        self.assertEqual(self.post_count, 1)

    def test_tenants_never_reuse_each_others_intent(self):
        a, b = self._emit(), self._emit(2)
        self.assertNotEqual(a['externalReference'], b['externalReference'])
        self.assertNotEqual(a['id'], b['id'])
        with self.assertRaises(ValueError):
            self._emit(clienteId=2, ucId=2)
        with self.app.test_request_context('/'):
            g.current_empresa_id = 1
            self.assertIsNone(service.obter(b['id'], 1))
        self.assertEqual(self.post_count, 2)

    def test_service_itself_rejects_readonly_actor_and_foreign_tenant(self):
        with self.app.app_context():
            User.query.filter_by(id=1).update({'role': 'operator'})
            db.session.commit()
        with self.assertRaises(PermissionError):
            self._emit()
        with self.app.test_request_context('/'):
            g.current_empresa_id = 2
            with self.assertRaises(PermissionError):
                service.emitir({}, 1, 1)
        self.assertEqual(self._rows(), [])
        self.asaas.criar_cobranca.assert_not_called()

    def test_invalid_financial_inputs_never_create_intent(self):
        for data in ({'valor': 'NaN'}, {'valor': 'Infinity'}, {'valor': -1},
                     {'valor': '100000000'}, {'competencia': '2026-13'},
                     {'competencia': []}, {'ucId': True}, {'clienteId': []}):
            with self.subTest(data=data), self.assertRaises(ValueError):
                self._emit(**data)
        self.assertEqual(self._rows(), [])
        self.asaas.criar_cobranca.assert_not_called()

    def test_sync_recovers_intent_without_reposting(self):
        self.asaas.criar_cobranca.side_effect = AsaasError('unknown')
        with self.assertRaises(service.EmissaoPendente):
            self._emit()
        row = self._rows()[0]
        self.remote[row['external_reference']] = dict(id='pay_delayed', status='PENDING',
            externalReference=row['external_reference'], customer='cus_1', value=10,
            dueDate='2026-10-05', billingType='BOLETO')
        with self.app.test_request_context('/'):
            g.current_empresa_id = 1
            self.assertEqual(service.sincronizar(service.obter(row['id'], 1))['asaasId'], 'pay_delayed')
        self.asaas.criar_cobranca.assert_called_once()

    def test_crash_after_reservation_does_not_expire_or_repost(self):
        self.asaas.criar_cobranca.side_effect = SystemExit('worker stopped')
        with self.assertRaises(SystemExit):
            self._emit()
        with self.assertRaises(service.EmissaoPendente):
            self._emit()
        self.asaas.criar_cobranca.assert_called_once()

    def test_database_uniqueness_cannot_be_bypassed_by_python(self):
        self._emit()
        row = self._rows()[0]
        for column in ('external_reference', 'emission_key'):
            with self.app.app_context():
                duplicate = dict(row)
                duplicate.pop('id')
                duplicate.pop('created_at'); duplicate.pop('updated_at')
                duplicate['mes_vencimento'] = date(2026, 10, 5)
                duplicate['emissao_iniciada_em'] = None
                duplicate['asaas_id'] = None
                if column == 'external_reference': duplicate['emission_key'] = 'different'
                else: duplicate['external_reference'] = 'different'
                db.session.add(Fatura(**duplicate))
                with self.assertRaises(IntegrityError):
                    db.session.commit()
                db.session.rollback()

    def test_pending_route_is_409_and_null_id_cannot_cancel_or_match_webhook(self):
        self.asaas.criar_cobranca.side_effect = AsaasError('unknown')
        with self.app.app_context():
            token = generate_token(1)
        client = self.app.test_client()
        headers = {'Authorization': f'Bearer {token}'}
        response = client.post('/api/v1/faturas', headers=headers, json=dict(
            clienteId=1, ucId=1, valor=10, competencia='2026-09', mesVencimento='2026-10-05'))
        self.assertEqual(response.status_code, 409)
        fatura_id = response.json['details']['faturaId']
        self.assertEqual(client.post(f'/api/v1/faturas/{fatura_id}/cancelar', headers=headers).status_code, 409)
        with self.app.test_request_context('/'):
            g.current_empresa_id = 1
            response = self.app.test_client().post('/api/v1/webhooks/asaas', json={
                'id': 'evt-invalid', 'event': 'PAYMENT_RECEIVED', 'payment': {'status': 'RECEIVED'},
            })
            self.assertEqual(response.status_code, 400)
            self.assertEqual(service.resumo(1)['pending'], 0)
        self.asaas.cancelar_cobranca.assert_not_called()


if __name__ == '__main__':
    unittest.main()
