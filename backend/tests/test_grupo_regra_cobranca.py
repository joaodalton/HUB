import os
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex

_DB = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_DB.close()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from extensions import db
from models.empresa import Empresa
from models.fatura import Fatura
from models.grupo_regra_cobranca import GrupoRegraCobranca
from models.regra_cobranca_assignment import RegraCobrancaAssignment
from models.user import User
from utils.auth import generate_token
try:
    from .support import IsolatedTestRuntime
except ImportError:
    from support import IsolatedTestRuntime


class GrupoRegraCobrancaTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        uri = f"sqlite:///{_DB.name.replace(chr(92), '/')}"
        cls.prepare_test_runtime(uri, 'billing-rule-test', limiter_enabled=False)
        cls.app = create_app()
        with cls.app.app_context():
            db.create_all()
            db.session.add_all([
                Empresa(id=1, nome='Empresa A', slug='billing-rule-a'),
                Empresa(id=2, nome='Empresa B', slug='billing-rule-b'),
            ])
            db.session.add_all([
                User(
                    empresa_id=1, nome=role.title(), email=f'{role}@a.test',
                    password_hash='x', role=role,
                )
                for role in ('owner', 'admin', 'financial', 'operator', 'viewer')
            ])
            db.session.add(User(
                empresa_id=2, nome='Owner B', email='owner@b.test',
                password_hash='x', role='owner',
            ))
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
            GrupoRegraCobranca.query.delete()
            db.session.commit()

    @staticmethod
    def _payload(**overrides):
        payload = {
            'nome': 'Regra comercial',
            'descricao': 'Perfil reutilizavel',
            'calculationMethod': 'energia_compensada',
            'tariffSource': 'manual',
            'manualTariff': '0.654321',
            'discountType': 'percentage',
            'discountValue': '12.345678',
            'tariffBasis': 'compensated',
            'billingMode': 'auto',
            'dueDateBasis': 'invoice_due_date',
            'dueDateOffsetDays': -2,
            'monthlyInterest': '1.234567',
            'finePercentage': '2.000001',
        }
        payload.update(overrides)
        return payload

    def _token(self, email):
        with self.app.app_context():
            return generate_token(self.users[email])

    def _request(self, email, method='GET', path='/api/v1/billing-rules', body=None):
        return self.app.test_client().open(
            path, method=method,
            headers={'Authorization': f'Bearer {self._token(email)}'},
            json=body,
        )

    def test_create_persists_contract_enums_decimals_offset_and_tenant(self):
        response = self._request('owner@a.test', 'POST', body=self._payload())
        self.assertEqual(response.status_code, 201)
        row = response.json['data']
        self.assertEqual(row['empresaId'], 1)
        self.assertEqual(row['calculationMethod'], 'energia_compensada')
        self.assertEqual(row['tariffSource'], 'manual')
        self.assertEqual(row['billingMode'], 'auto')
        self.assertEqual(row['dueDateBasis'], 'invoice_due_date')
        self.assertEqual(row['dueDateOffsetDays'], -2)
        self.assertEqual(row['revision'], 1)
        for field, value in (
            ('manualTariff', '0.654321'), ('discountValue', '12.345678'),
            ('monthlyInterest', '1.234567'), ('finePercentage', '2.000001'),
        ):
            self.assertEqual(row[field], value)
            self.assertIsInstance(row[field], str)
        with self.app.app_context():
            item = GrupoRegraCobranca.query.one()
            self.assertEqual(item.manual_tariff, Decimal('0.654321'))
            self.assertEqual(item.empresa_id, 1)
            self.assertEqual(Fatura.query.count(), 0)

    def test_structural_validation_rejects_missing_or_extraneous_values(self):
        cases = [
            (self._payload(manualTariff=None), 'manualTariff'),
            (self._payload(discountValue=None), 'discountValue'),
            (self._payload(discountType='none', discountValue='0'), 'discountValue'),
            (self._payload(monthlyInterest='NaN'), 'monthlyInterest'),
            (self._payload(finePercentage='Infinity'), 'finePercentage'),
            (self._payload(tariffBasis='documented_component'), 'energyComponentIndex'),
            ({**self._payload(), 'empresaId': 2}, 'empresaId'),
        ]
        for payload, field in cases:
            with self.subTest(field=field):
                response = self._request('owner@a.test', 'POST', body=payload)
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json['error'])

    def test_documented_component_reference_and_no_discount_are_valid(self):
        payload = self._payload(
            tariffBasis='documented_component', energyComponentIndex=0,
            discountType='none', discountValue=None,
        )
        response = self._request('owner@a.test', 'POST', body=payload)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json['data']['energyComponentIndex'], 0)
        self.assertIsNone(response.json['data']['discountValue'])

    def test_cross_tenant_read_and_update_are_not_found(self):
        created = self._request('owner@b.test', 'POST', body=self._payload())
        rule_id = created.json['data']['id']
        self.assertEqual(
            self._request('owner@a.test', path=f'/api/v1/billing-rules/{rule_id}').status_code,
            404,
        )
        self.assertEqual(
            self._request(
                'owner@a.test', 'PATCH', f'/api/v1/billing-rules/{rule_id}', {'ativo': False},
            ).status_code,
            404,
        )
        self.assertEqual(self._request('owner@a.test').json['data'], [])

    def test_default_is_optional_unique_per_tenant_and_database_enforced(self):
        none = self._request('owner@a.test', 'POST', body=self._payload(nome='Sem default'))
        self.assertEqual(none.status_code, 201)
        self.assertFalse(none.json['data']['padrao'])

        first = self._request(
            'owner@a.test', 'PATCH',
            f"/api/v1/billing-rules/{none.json['data']['id']}", {'padrao': True},
        )
        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.json['data']['padrao'])
        conflict = self._request('owner@a.test', 'POST', body=self._payload(nome='Outro default', padrao=True))
        self.assertEqual((conflict.status_code, conflict.json['code']), (409, 'DEFAULT_BILLING_RULE_CONFLICT'))

        other_tenant = self._request('owner@b.test', 'POST', body=self._payload(nome='Default B', padrao=True))
        self.assertEqual(other_tenant.status_code, 201)

    def test_deactivate_and_financial_update_have_controlled_revision(self):
        created = self._request('owner@a.test', 'POST', body=self._payload(padrao=True))
        rule_id = created.json['data']['id']
        deactivated = self._request(
            'owner@a.test', 'PATCH', f'/api/v1/billing-rules/{rule_id}', {'ativo': False},
        )
        self.assertEqual(deactivated.status_code, 200)
        self.assertFalse(deactivated.json['data']['ativo'])
        self.assertEqual(deactivated.json['data']['revision'], 1)

        revised = self._request(
            'owner@a.test', 'PATCH', f'/api/v1/billing-rules/{rule_id}',
            {'manualTariff': '0.654322'},
        )
        self.assertEqual(revised.status_code, 200)
        self.assertEqual(revised.json['data']['revision'], 2)
        self.assertEqual(revised.json['data']['manualTariff'], '0.654322')
        with self.app.app_context():
            self.assertEqual(Fatura.query.count(), 0)

    def test_active_assignment_blocks_rule_deactivation_only_in_its_tenant(self):
        linked = self._request('owner@a.test', 'POST', body=self._payload(nome='Vinculada')).json['data']
        free = self._request('owner@a.test', 'POST', body=self._payload(nome='Livre')).json['data']
        other = self._request('owner@b.test', 'POST', body=self._payload(nome='Empresa B')).json['data']

        for rule, owner in ((linked, 'owner@a.test'), (other, 'owner@b.test')):
            response = self._request(
                owner, 'POST', '/api/v1/billing-rule-assignments',
                {'grupoRegraCobrancaId': rule['id'], 'scopeType': 'company'},
            )
            self.assertEqual(response.status_code, 201, response.json)
            if owner == 'owner@a.test':
                assignment_id = response.json['data']['id']

        blocked = self._request(
            'owner@a.test', 'PATCH', f"/api/v1/billing-rules/{linked['id']}", {'ativo': False},
        )
        self.assertEqual(blocked.status_code, 409, blocked.json)
        self.assertEqual(blocked.json['code'], 'BILLING_RULE_IN_USE')
        self.assertTrue(self._request('owner@a.test', path=f"/api/v1/billing-rules/{linked['id']}").json['data']['ativo'])

        deactivated = self._request(
            'owner@a.test', 'PATCH', f"/api/v1/billing-rules/{free['id']}", {'ativo': False},
        )
        self.assertEqual(deactivated.status_code, 200, deactivated.json)
        self.assertFalse(deactivated.json['data']['ativo'])

        self.assertEqual(self._request(
            'owner@a.test', 'PATCH', f'/api/v1/billing-rule-assignments/{assignment_id}',
            {'ativo': False},
        ).status_code, 200)
        released = self._request(
            'owner@a.test', 'PATCH', f"/api/v1/billing-rules/{linked['id']}", {'ativo': False},
        )
        self.assertEqual(released.status_code, 200, released.json)

    def test_rbac_reads_for_financial_viewers_writes_only_financial_roles(self):
        for role in ('owner', 'admin', 'financial', 'operator', 'viewer'):
            self.assertEqual(self._request(f'{role}@a.test').status_code, 200)
        for role in ('owner', 'admin', 'financial'):
            self.assertEqual(
                self._request(f'{role}@a.test', 'POST', body=self._payload(nome=role)).status_code,
                201,
            )
        for role in ('operator', 'viewer'):
            self.assertEqual(
                self._request(f'{role}@a.test', 'POST', body=self._payload(nome=role)).status_code,
                403,
            )

    def test_group_creation_does_not_create_assignment_or_calculation(self):
        self._request('owner@a.test', 'POST', body=self._payload(padrao=True))
        with self.app.app_context():
            self.assertEqual(RegraCobrancaAssignment.query.count(), 0)
            self.assertEqual(Fatura.query.count(), 0)

    def test_default_partial_index_compiles_for_postgresql(self):
        index = next(
            item for item in GrupoRegraCobranca.__table__.indexes
            if item.name == 'uq_grupos_regra_cobranca_default_ativo'
        )
        sql = str(CreateIndex(index).compile(dialect=postgresql.dialect()))
        self.assertIn('CREATE UNIQUE INDEX', sql)
        self.assertIn('WHERE ativo IS TRUE AND padrao IS TRUE', sql)

    def test_c41_methods_and_company_tariff_independent_of_documentary_source(self):
        for method in ('valor_total_fatura', 'tarifa_fixa_com_desconto', 'tarifa_especifica', 'energia_recebida'):
            payload = self._payload(calculationMethod=method, tariffSource='invoice')
            del payload['manualTariff']
            payload['tariffConfiguration'] = {'companyTariff': '0.734821'}
            response = self._request('owner@a.test', 'POST', body=payload)
            self.assertEqual(response.status_code, 201, response.json)
            self.assertEqual(response.json['data']['tariffConfiguration']['companyTariff'], '0.734821')
        for method in ('valor_total_fatura', 'energia_recebida'):
            response = self._request('owner@a.test', 'POST', body=self._payload(
                calculationMethod=method, tariffSource='invoice', manualTariff=None))
            self.assertEqual(response.status_code, 201, response.json)
        with self.app.app_context():
            self.assertEqual(Fatura.query.count(), 0)

    def test_fixed_with_uc_discount_can_be_configured_without_group_discount(self):
        payload = self._payload(
            calculationMethod='tarifa_fixa_com_desconto', discountType='none', discountValue=None,
        )
        created = self._request('owner@a.test', 'POST', body=payload)
        self.assertEqual(created.status_code, 201, created.json)
        rule_id = created.json['data']['id']
        self.assertEqual((created.json['data']['discountType'], created.json['data']['discountValue']),
                         ('none', None))
        self.assertEqual(self._request('owner@b.test', path=f'/api/v1/billing-rules/{rule_id}').status_code, 404)
        changed = self._request('owner@a.test', 'PATCH', f'/api/v1/billing-rules/{rule_id}',
                                {'discountType': 'percentage', 'discountValue': '10'})
        self.assertEqual(changed.status_code, 200, changed.json)
        self.assertEqual(changed.json['data']['discountValue'], '10.000000')
        restored = self._request('owner@a.test', 'PATCH', f'/api/v1/billing-rules/{rule_id}',
                                 {'discountType': 'none', 'discountValue': None})
        self.assertEqual(restored.status_code, 200, restored.json)

    def test_c41_structural_validation(self):
        cases = [
            {'calculationMethod': 'tarifa_especifica', 'tariffSource': 'invoice', 'manualTariff': None},
            {'calculationMethod': 'tarifa_fixa_com_desconto', 'discountType': 'fixed'},
            {'tariffConfiguration': {'companyTariff': '0.999999'}},
            {'tariffConfiguration': {'tariffHp': '0.1234567'}},
            {'tariffConfiguration': {'tariffHp': '1E999999999'}},
            {'billingModifiers': {'icmsPolicy': 'include'}},
            {'billingModifiers': {'excludePisCofins': 'false'}},
            {'billingModifiers': {'recurringAdditionalCost': 1.2}},
            {'billingModifiers': {'gracePeriod': {'enabled': True, 'start': '2026-09-01'}}},
            {'billingModifiers': {'gracePeriod': {'enabled': True, 'start': '2026-10-01', 'end': '2026-09-01'}}},
            {'billingModifiers': {'gracePeriod': {'enabled': False, 'withoutDiscount': True}}},
            {'billingModifiers': {'gracePeriod': {'enabled': True, 'start': 'bad', 'end': '2026-10-01'}}},
            {'billingModifiers': {'gracePeriod': {'enabled': True, 'durationMonths': 0}}},
            {'billingModifiers': {'gracePeriod': {'enabled': True, 'durationMonths': True}}},
            {'billingModifiers': {'gracePeriod': {'enabled': False, 'durationMonths': 3}}},
            {'billingModifiers': {'unknown': True}},
        ]
        for overrides in cases:
            with self.subTest(overrides=overrides):
                response = self._request('owner@a.test', 'POST', body=self._payload(**overrides))
                self.assertEqual(response.status_code, 400, response.json)

    def test_c41_financial_fields_revision_nested_patch_and_decimal_roundtrip(self):
        created = self._request('owner@a.test', 'POST', body=self._payload()).json['data']
        path = f"/api/v1/billing-rules/{created['id']}"
        revision = 1
        patches = [
            {'calculationMethod': 'tarifa_especifica'},
            {'tariffConfiguration': {'companyTariff': '0.734821'}},
            {'tariffConfiguration': {'tariffHfp': '0.345678'}},
            {'tariffConfiguration': {'tariffHp': '0.456789'}},
            {'billingModifiers': {'excludePisCofins': True}},
            {'billingModifiers': {'icmsPolicy': 'exclude'}},
            {'billingModifiers': {'excludeTariffFlag': True}},
            {'billingModifiers': {'gracePeriod': {'enabled': True, 'withoutDiscount': True}}},
            {'billingModifiers': {'gracePeriod': {'durationMonths': 3}}},
            {'billingModifiers': {'recurringAdditionalCost': '12.345678'}},
            {'tariffConfiguration': {'tariffHp': None}},
        ]
        for payload in patches:
            response = self._request('owner@a.test', 'PATCH', path, payload)
            self.assertEqual(response.status_code, 200, response.json)
            revision += 1
            self.assertEqual(response.json['data']['revision'], revision)
            repeat = self._request('owner@a.test', 'PATCH', path, payload)
            self.assertEqual(repeat.json['data']['revision'], revision)
        final = self._request('owner@a.test', 'PATCH', path, {'descricao': 'Descritivo'}).json['data']
        self.assertEqual(final['revision'], revision)
        self.assertEqual(final['tariffConfiguration'], {
            'companyTariff': '0.734821', 'tariffHfp': '0.345678', 'tariffHp': None})
        self.assertEqual(final['billingModifiers']['recurringAdditionalCost'], '12.345678')
        self.assertEqual(final['billingModifiers']['gracePeriod']['durationMonths'], 3)
        self.assertIsNone(final['billingModifiers']['gracePeriod']['start'])
        with self.app.app_context():
            group = db.session.get(GrupoRegraCobranca, created['id'])
            self.assertEqual(group.tariff_hfp, Decimal('0.345678'))
            self.assertIsNone(group.tariff_hp)
            self.assertEqual(group.recurring_additional_cost, Decimal('12.345678'))
            self.assertEqual(Fatura.query.count(), 0)

    def test_c41_unconfigured_fields_remain_null_and_new_fields_are_tenant_scoped(self):
        result = self._request('owner@b.test', 'POST', body=self._payload()).json['data']
        self.assertIsNone(result['tariffConfiguration']['tariffHp'])
        self.assertIsNone(result['tariffConfiguration']['tariffHfp'])
        modifiers = result['billingModifiers']
        self.assertTrue(all(value is None for key, value in modifiers.items() if key != 'gracePeriod'))
        self.assertTrue(all(value is None for value in modifiers['gracePeriod'].values()))
        response = self._request('owner@a.test', 'PATCH', f"/api/v1/billing-rules/{result['id']}",
                                 {'billingModifiers': {'icmsPolicy': 'exclude'}})
        self.assertEqual(response.status_code, 404)

    def test_c42_legacy_dates_preserved_until_explicit_review_and_clearing(self):
        from datetime import date
        created = self._request('owner@a.test', 'POST', body=self._payload()).json['data']
        path = f"/api/v1/billing-rules/{created['id']}"
        with self.app.app_context():
            group = db.session.get(GrupoRegraCobranca, created['id'])
            group.grace_enabled = True
            group.grace_without_discount = True
            group.grace_start, group.grace_end = date(2026, 9, 1), date(2026, 9, 30)
            db.session.commit()
        descriptive = self._request('owner@a.test', 'PATCH', path, {'descricao': 'Revisar legado'})
        self.assertEqual(descriptive.status_code, 200)
        self.assertEqual(descriptive.json['data']['billingModifiers']['gracePeriod']['start'], '2026-09-01')
        self.assertEqual(descriptive.json['data']['revision'], 1)
        invalid = self._request('owner@a.test', 'PATCH', path,
            {'billingModifiers': {'gracePeriod': {'start': None}}})
        self.assertEqual(invalid.status_code, 400)
        cleared = self._request('owner@a.test', 'PATCH', path,
            {'billingModifiers': {'gracePeriod': {'start': None, 'end': None, 'durationMonths': 3}}})
        self.assertEqual(cleared.status_code, 200, cleared.json)
        self.assertEqual(cleared.json['data']['revision'], 2)
        self.assertEqual(cleared.json['data']['billingModifiers']['gracePeriod'], {
            'enabled': True, 'withoutDiscount': True, 'durationMonths': 3, 'start': None, 'end': None})


if __name__ == '__main__':
    unittest.main()
