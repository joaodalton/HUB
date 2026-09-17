import os
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex


_DB = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_DB.close()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from extensions import db
from models.client import Client
from models.consumer_unit import ConsumerUnit
from models.empresa import Empresa
from models.fatura import Fatura
from models.grupo_regra_cobranca import GrupoRegraCobranca
from models.regra_cobranca_assignment import RegraCobrancaAssignment
from models.user import User
from services import regra_cobranca_assignment_service as assignment_service
from utils.auth import generate_token
try:
    from .support import IsolatedTestRuntime
except ImportError:
    from support import IsolatedTestRuntime


class RegraCobrancaAssignmentTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        uri = f"sqlite:///{_DB.name.replace(chr(92), '/')}"
        cls.prepare_test_runtime(uri, 'assignment-test', limiter_enabled=False)
        cls.app = create_app()
        with cls.app.app_context():
            db.create_all()
            db.session.add_all([
                Empresa(id=1, nome='Empresa A', slug='assignment-a'),
                Empresa(id=2, nome='Empresa B', slug='assignment-b'),
            ])
            db.session.add_all([
                User(
                    empresa_id=1, nome=role.title(), email=f'{role}@a.test',
                    password_hash='x', role=role,
                )
                for role in ('owner', 'admin', 'financial', 'operator', 'viewer')
            ] + [
                User(
                    empresa_id=2, nome='Owner B', email='owner@b.test',
                    password_hash='x', role='owner',
                ),
                Client(id=1, empresa_id=1, nome='Cliente A', cpf='11111111111', email='a@test'),
                Client(id=2, empresa_id=2, nome='Cliente B', cpf='22222222222', email='b@test'),
                ConsumerUnit(id=1, empresa_id=1, client_id=1, codigo='UC-A'),
                ConsumerUnit(id=2, empresa_id=2, client_id=2, codigo='UC-B'),
            ])
            db.session.flush()
            db.session.add_all([
                cls._rule(1, 1, 'Regra A1'), cls._rule(2, 1, 'Regra A2'),
                cls._rule(3, 1, 'Regra inativa', ativo=False),
                cls._rule(4, 2, 'Regra B'),
            ])
            db.session.commit()
            cls.users = {
                user.email: user.id for user in db.session.execute(db.select(User)).scalars()
            }

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        os.unlink(_DB.name)
        cls.restore_test_runtime()

    def tearDown(self):
        with self.app.app_context():
            RegraCobrancaAssignment.query.delete()
            db.session.commit()

    @staticmethod
    def _rule(rule_id, empresa_id, nome, ativo=True):
        return GrupoRegraCobranca(
            id=rule_id, empresa_id=empresa_id, nome=nome, ativo=ativo, padrao=False,
            calculation_method='energia_compensada', tariff_source='manual',
            manual_tariff=Decimal('0.123456'), discount_type='none', discount_value=None,
            tariff_basis='compensated', billing_mode='auto',
            due_date_basis='invoice_due_date', due_date_offset_days=0, revision=1,
        )

    def _token(self, email):
        with self.app.app_context():
            return generate_token(self.users[email])

    def _request(self, email, method='GET', path='/api/v1/billing-rule-assignments', body=None):
        return self.app.test_client().open(
            path, method=method,
            headers={'Authorization': f'Bearer {self._token(email)}'}, json=body,
        )

    def test_company_client_and_consumer_unit_assignments_are_explicit_and_serialized(self):
        cases = [
            ({'grupoRegraCobrancaId': 1, 'scopeType': 'company'}, None, None),
            ({'grupoRegraCobrancaId': 1, 'scopeType': 'client', 'clientId': 1}, 1, None),
            ({'grupoRegraCobrancaId': 1, 'scopeType': 'consumer_unit', 'consumerUnitId': 1}, None, 1),
        ]
        for body, client_id, uc_id in cases:
            response = self._request('owner@a.test', 'POST', body=body)
            self.assertEqual(response.status_code, 201, response.json)
            item = response.json['data']
            self.assertEqual(item['empresaId'], 1)
            self.assertEqual(item['clientId'], client_id)
            self.assertEqual(item['consumerUnitId'], uc_id)
            self.assertTrue(item['ativo'])

        filtered = self._request(
            'owner@a.test', path='/api/v1/billing-rule-assignments?scopeType=client&clientId=1&ativo=true',
        )
        self.assertEqual(len(filtered.json['data']), 1)
        self.assertEqual(filtered.json['data'][0]['scopeType'], 'client')

    def test_scope_invariants_are_rejected_by_api(self):
        cases = [
            {'grupoRegraCobrancaId': 1, 'scopeType': 'company', 'clientId': 1},
            {'grupoRegraCobrancaId': 1, 'scopeType': 'company', 'consumerUnitId': 1},
            {'grupoRegraCobrancaId': 1, 'scopeType': 'client'},
            {'grupoRegraCobrancaId': 1, 'scopeType': 'client', 'clientId': 1, 'consumerUnitId': 1},
            {'grupoRegraCobrancaId': 1, 'scopeType': 'consumer_unit'},
            {'grupoRegraCobrancaId': 1, 'scopeType': 'consumer_unit', 'clientId': 1, 'consumerUnitId': 1},
        ]
        for body in cases:
            with self.subTest(body=body):
                response = self._request('owner@a.test', 'POST', body=body)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json['code'], 'INVALID_BILLING_RULE_ASSIGNMENT')

    def test_relationships_must_belong_to_current_tenant(self):
        cases = [
            {'grupoRegraCobrancaId': 4, 'scopeType': 'company'},
            {'grupoRegraCobrancaId': 1, 'scopeType': 'client', 'clientId': 2},
            {'grupoRegraCobrancaId': 1, 'scopeType': 'consumer_unit', 'consumerUnitId': 2},
            {'grupoRegraCobrancaId': 1, 'scopeType': 'company', 'empresaId': 2},
        ]
        for body in cases:
            with self.subTest(body=body):
                self.assertEqual(self._request('owner@a.test', 'POST', body=body).status_code, 400)

    def test_cross_tenant_assignment_is_not_visible_or_mutable(self):
        created = self._request(
            'owner@b.test', 'POST', body={'grupoRegraCobrancaId': 4, 'scopeType': 'company'},
        )
        assignment_id = created.json['data']['id']
        self.assertEqual(
            self._request('owner@a.test', path=f'/api/v1/billing-rule-assignments/{assignment_id}').status_code,
            404,
        )
        self.assertEqual(
            self._request(
                'owner@a.test', 'PATCH', f'/api/v1/billing-rule-assignments/{assignment_id}',
                {'ativo': False},
            ).status_code,
            404,
        )
        self.assertEqual(self._request('owner@a.test').json['data'], [])

    def test_database_allows_only_one_active_assignment_per_target(self):
        payloads = [
            {'grupoRegraCobrancaId': 1, 'scopeType': 'company'},
            {'grupoRegraCobrancaId': 1, 'scopeType': 'client', 'clientId': 1},
            {'grupoRegraCobrancaId': 1, 'scopeType': 'consumer_unit', 'consumerUnitId': 1},
        ]
        for payload in payloads:
            with self.subTest(scope=payload['scopeType']):
                self.assertEqual(self._request('owner@a.test', 'POST', body=payload).status_code, 201)
                conflict = self._request(
                    'owner@a.test', 'POST', body={**payload, 'grupoRegraCobrancaId': 2},
                )
                self.assertEqual((conflict.status_code, conflict.json['code']), (409, 'BILLING_RULE_ASSIGNMENT_CONFLICT'))
                self._request(
                    'owner@a.test', 'PATCH',
                    f"/api/v1/billing-rule-assignments/{self._request('owner@a.test').json['data'][0]['id']}",
                    {'ativo': False},
                )

        other = self._request(
            'owner@b.test', 'POST', body={'grupoRegraCobrancaId': 4, 'scopeType': 'company'},
        )
        self.assertEqual(other.status_code, 201)

    def test_inactive_group_rejects_active_assignment_but_allows_inactive_history(self):
        active = self._request(
            'owner@a.test', 'POST', body={'grupoRegraCobrancaId': 3, 'scopeType': 'company'},
        )
        self.assertEqual(active.status_code, 400)
        inactive = self._request(
            'owner@a.test', 'POST',
            body={'grupoRegraCobrancaId': 3, 'scopeType': 'company', 'ativo': False},
        )
        self.assertEqual(inactive.status_code, 201)
        self.assertFalse(inactive.json['data']['ativo'])

    def test_rule_swap_is_atomic_and_preserves_inactive_history(self):
        old = self._request(
            'owner@a.test', 'POST',
            body={'grupoRegraCobrancaId': 1, 'scopeType': 'client', 'clientId': 1},
        ).json['data']
        inactive_group = self._request(
            'owner@a.test', 'PATCH', f"/api/v1/billing-rule-assignments/{old['id']}",
            {'grupoRegraCobrancaId': 3},
        )
        self.assertEqual(inactive_group.status_code, 400)
        switched = self._request(
            'owner@a.test', 'PATCH', f"/api/v1/billing-rule-assignments/{old['id']}",
            {'grupoRegraCobrancaId': 2},
        )
        self.assertEqual(switched.status_code, 200, switched.json)
        self.assertNotEqual(switched.json['data']['id'], old['id'])
        with self.app.app_context():
            rows = RegraCobrancaAssignment.query.order_by(RegraCobrancaAssignment.id).all()
            self.assertEqual([(row.grupo_regra_cobranca_id, row.ativo) for row in rows], [(1, False), (2, True)])
            self.assertEqual(Fatura.query.count(), 0)

        disabled = self._request(
            'owner@a.test', 'PATCH',
            f"/api/v1/billing-rule-assignments/{switched.json['data']['id']}", {'ativo': False},
        )
        self.assertEqual(disabled.status_code, 200)
        self.assertFalse(disabled.json['data']['ativo'])
        self.assertEqual(self._request(
            'owner@a.test', 'DELETE',
            f"/api/v1/billing-rule-assignments/{switched.json['data']['id']}",
        ).status_code, 405)

    def test_rbac_reuses_billing_rule_permissions(self):
        for role in ('owner', 'admin', 'financial', 'operator', 'viewer'):
            self.assertEqual(self._request(f'{role}@a.test').status_code, 200)
        for role in ('owner', 'admin', 'financial'):
            response = self._request(
                f'{role}@a.test', 'POST',
                body={'grupoRegraCobrancaId': 1, 'scopeType': 'company', 'ativo': False},
            )
            self.assertEqual(response.status_code, 201)
        for role in ('operator', 'viewer'):
            self.assertEqual(self._request(
                f'{role}@a.test', 'POST',
                body={'grupoRegraCobrancaId': 1, 'scopeType': 'company'},
            ).status_code, 403)

    def test_concurrent_requests_never_leave_two_active_targets(self):
        token = self._token('owner@a.test')

        def run(body):
            return self.app.test_client().post(
                '/api/v1/billing-rule-assignments', json=body,
                headers={'Authorization': f'Bearer {token}'},
            ).status_code

        for target in (
            {'scopeType': 'client', 'clientId': 1},
            {'scopeType': 'consumer_unit', 'consumerUnitId': 1},
        ):
            barrier = threading.Barrier(2)
            bodies = [{**target, 'grupoRegraCobrancaId': rule_id} for rule_id in (1, 2)]
            original_commit = assignment_service._commit

            def synchronized_commit():
                barrier.wait(timeout=5)
                return original_commit()

            with patch.object(assignment_service, '_commit', synchronized_commit):
                with ThreadPoolExecutor(max_workers=2) as executor:
                    statuses = list(executor.map(run, bodies))
            self.assertEqual(sorted(statuses), [201, 409])
            with self.app.app_context():
                self.assertEqual(RegraCobrancaAssignment.query.filter_by(ativo=True).count(), 1)
                RegraCobrancaAssignment.query.delete()
                db.session.commit()

    def test_partial_indexes_compile_for_postgresql(self):
        names = {
            'uq_regra_assignment_company_ativo',
            'uq_regra_assignment_client_ativo',
            'uq_regra_assignment_uc_ativo',
        }
        indexes = {index.name: index for index in RegraCobrancaAssignment.__table__.indexes}
        for name in names:
            sql = str(CreateIndex(indexes[name]).compile(dialect=postgresql.dialect()))
            self.assertIn('CREATE UNIQUE INDEX', sql)
            self.assertIn('WHERE ativo IS TRUE', sql)


if __name__ == '__main__':
    unittest.main()
