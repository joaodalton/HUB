import sys
import tempfile
import unittest
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from flask import g
from sqlalchemy import event
from sqlalchemy.exc import OperationalError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from extensions import db
from models.client import Client
from models.consumer_unit import ConsumerUnit
from models.empresa import Empresa
from models.grupo_regra_cobranca import GrupoRegraCobranca
from models.regra_cobranca_assignment import RegraCobrancaAssignment
from services import billing_rule_resolver as service
from services.billing_calculation_contracts import BillingRuleScope, ResolvedBillingRule, BillingRuleSnapshot
try:
    from .support import IsolatedTestRuntime
except ImportError:
    from support import IsolatedTestRuntime


class RuleResolverTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.prepare_test_runtime('sqlite:///' + (Path(cls.temp.name) / 'resolver.db').as_posix(),
                                 'resolver-test', limiter_enabled=False)
        cls.app = create_app()

    @classmethod
    def tearDownClass(cls):
        cls.restore_test_runtime()
        cls.temp.cleanup()

    def setUp(self):
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        db.session.add_all([
            Empresa(id=10, nome='A', slug='resolver-a'),
            Empresa(id=20, nome='B', slug='resolver-b'),
            Client(id=11, empresa_id=10, nome='A1', cpf='111', email='a1@test'),
            Client(id=12, empresa_id=10, nome='A2', cpf='112', email='a2@test'),
            Client(id=21, empresa_id=20, nome='B1', cpf='221', email='b1@test'),
            ConsumerUnit(id=101, empresa_id=10, client_id=11, codigo='A1'),
            ConsumerUnit(id=102, empresa_id=10, client_id=12, codigo='A2'),
            ConsumerUnit(id=201, empresa_id=20, client_id=21, codigo='B1'),
        ])
        db.session.flush()
        for rule_id, tenant in ((1, 10), (2, 10), (3, 10), (4, 20)):
            db.session.add(GrupoRegraCobranca(
                id=rule_id, empresa_id=tenant, nome=f'Perfil {rule_id}',
                ativo=True, padrao=False, revision=rule_id + 2,
                calculation_method='energia_compensada', tariff_source='manual',
                manual_tariff=Decimal(f'0.{rule_id}23456'),
                discount_type='percentage', discount_value=Decimal(f'{rule_id}.234567'),
                tariff_basis='compensated', billing_mode='auto',
                due_date_basis='invoice_due_date', due_date_offset_days=-rule_id,
                monthly_interest=Decimal(f'{rule_id}.000001'), fine_percentage=None,
            ))
        db.session.commit()
        g.current_empresa_id = 10
        self.resolver = service.RuleResolver()

    def tearDown(self):
        db.session.rollback()
        db.session.remove()
        g.pop('current_empresa_id', None)
        db.drop_all()
        db.engine.dispose()
        self.context.pop()

    def assign(self, scope, rule_id=1, *, active=True, tenant=10, target=None):
        row = RegraCobrancaAssignment(
            empresa_id=tenant, grupo_regra_cobranca_id=rule_id,
            scope_type=scope, ativo=active,
            client_id=(target or 11) if scope == 'client' else None,
            consumer_unit_id=(target or 101) if scope == 'consumer_unit' else None,
        )
        db.session.add(row)
        db.session.commit()
        return row

    def resolve(self, client=11, uc=101):
        return self.resolver.resolve(client_id=client, consumer_unit_id=uc)

    def blocked(self, code, **kwargs):
        with self.assertRaises(service.RuleResolutionError) as caught:
            self.resolve(**kwargs)
        self.assertEqual(caught.exception.code, code)

    def test_company_only_with_and_without_uc(self):
        self.assign('company')
        for uc in (None, 101):
            result = self.resolve(uc=uc)
            self.assertIs(type(result), ResolvedBillingRule)
            self.assertEqual((result.rule_id, result.source_scope, result.source_id),
                             (1, BillingRuleScope.COMPANY, 10))

    def test_c41_snapshot_transports_commercial_configuration_without_hp_fallback(self):
        group = db.session.get(GrupoRegraCobranca, 3)
        group.tariff_hfp = Decimal('0.734821')
        group.exclude_pis_cofins = True
        group.icms_policy = 'exclude'
        group.exclude_tariff_flag = True
        group.grace_enabled = True
        group.grace_without_discount = True
        group.recurring_additional_cost = Decimal('12.345678')
        self.assign('company', 1)
        self.assign('client', 2)
        self.assign('consumer_unit', 3)
        rule = self.resolve()
        self.assertEqual(rule.rule_id, 3)
        self.assertEqual(rule.rule_version, '5')
        self.assertTrue(rule.billing_modifiers.grace_period.requires_temporal_definition)
        snapshot = BillingRuleSnapshot(rule).to_dict()
        self.assertEqual(snapshot['tariff_configuration'], {
            'company_tariff': '0.323456', 'tariff_hfp': '0.734821', 'tariff_hp': None})
        self.assertEqual(snapshot['billing_modifiers']['icms_policy'], 'exclude')
        self.assertEqual(snapshot['billing_modifiers']['recurring_additional_cost'], '12.345678')
        self.assertEqual(snapshot['billing_modifiers']['grace_period'], {
            'enabled': True, 'without_discount': True, 'duration_months': None})

    def test_c42_legacy_global_grace_dates_block_without_lower_scope_fallback(self):
        from datetime import date
        group = db.session.get(GrupoRegraCobranca, 3)
        group.grace_enabled = True
        group.grace_start, group.grace_end = date(2026, 9, 1), date(2026, 9, 30)
        self.assign('company', 1)
        self.assign('consumer_unit', 3)
        self.blocked('grace_policy_migration_required')

    def test_c42_grace_policy_not_derived_from_uc_contract_date(self):
        from datetime import date
        group = db.session.get(GrupoRegraCobranca, 1)
        group.grace_enabled = True
        group.grace_without_discount = True
        group.grace_duration_months = 3
        db.session.get(ConsumerUnit, 101).inicio_contrato = date(2026, 9, 1)
        self.assign('company')
        policy = self.resolve().billing_modifiers.grace_period
        self.assertEqual(policy.duration_months, 3)
        self.assertTrue(policy.requires_temporal_definition)
        self.assertNotIn('start', asdict(policy))

    def test_client_wins_over_company_with_and_without_uc(self):
        self.assign('company')
        self.assign('client', 2)
        for uc in (None, 101):
            result = self.resolve(uc=uc)
            self.assertEqual((result.rule_id, result.source_scope, result.source_id),
                             (2, BillingRuleScope.CLIENT, 11))

    def test_uc_wins_and_returns_one_complete_rule(self):
        self.assign('company')
        self.assign('client', 2)
        assignment = self.assign('consumer_unit', 3)
        result = self.resolve()
        expected = ResolvedBillingRule(
            rule_id=3, rule_name='Perfil 3', rule_version='5',
            source_scope='consumer_unit', source_id=101,
            calculation_method='energia_compensada', tariff_source='manual',
            manual_tariff=Decimal('0.323456'), discount_type='percentage',
            discount_value=Decimal('3.234567'), tariff_basis='compensated',
            billing_mode='auto', due_date_basis='invoice_due_date', due_date_offset_days=-3,
            monthly_interest=Decimal('3.000001'), fine_percentage=None,
            metadata={'assignment_id': str(assignment.id)},
        )
        self.assertEqual(asdict(result), asdict(expected))
        self.assertIsInstance(result.manual_tariff, Decimal)
        self.assertIsInstance(result.discount_value, Decimal)

    def test_uc_without_assignment_uses_client(self):
        self.assign('client', 2)
        self.assertEqual(self.resolve().source_scope, BillingRuleScope.CLIENT)

    def test_no_assignments_is_explicit(self):
        self.blocked('no_rule_configured')

    def test_default_group_never_resolves_without_assignment(self):
        group = GrupoRegraCobranca.query.filter_by(id=1, empresa_id=10).one()
        group.padrao = True
        db.session.commit()
        self.blocked('no_rule_configured')
        self.assign('company', 2)
        self.assertEqual(self.resolve().rule_id, 2)

    def test_inactive_assignments_are_ignored_at_every_level(self):
        for scope in ('consumer_unit', 'client', 'company'):
            self.assign(scope, active=False)
        self.blocked('no_rule_configured')
        self.assign('company', 2)
        self.assertEqual(self.resolve().rule_id, 2)

    def test_inactive_group_blocks_instead_of_falling_back(self):
        for scope in ('consumer_unit', 'client', 'company'):
            with self.subTest(scope=scope):
                RegraCobrancaAssignment.query.delete()
                db.session.commit()
                if scope != 'company':
                    self.assign('company', 2)
                if scope == 'consumer_unit':
                    self.assign('client', 2)
                self.assign(scope)
                group = GrupoRegraCobranca.query.filter_by(id=1, empresa_id=10).one()
                group.ativo = False
                db.session.commit()
                self.blocked('inactive_rule_assigned')

    def test_uc_of_another_client_blocks_even_with_company(self):
        self.assign('company')
        self.blocked('invalid_context', uc=102)

    def test_other_tenant_and_missing_targets_are_indistinguishable(self):
        self.assign('company')
        for client, uc in ((21, None), (999, None), (11, 201), (11, 999)):
            with self.subTest(client=client, uc=uc):
                self.blocked('target_not_found', client=client, uc=uc)

    def test_other_tenant_assignments_cannot_influence_resolution(self):
        self.assign('company', 4, tenant=20)
        self.assign('client', 4, tenant=20, target=21)
        self.assign('consumer_unit', 4, tenant=20, target=201)
        self.blocked('no_rule_configured')
        g.current_empresa_id = 20
        result = self.resolve(client=21, uc=201)
        self.assertEqual((result.rule_id, result.source_id), (4, 201))

    def test_corrupt_cross_tenant_group_reference_blocks(self):
        self.assign('company', 1)
        self.assign('consumer_unit', 4)
        self.blocked('assignment_inconsistent')

    def test_ambiguous_assignments_block(self):
        row = self.assign('consumer_unit')
        # Simula dados legados sem índice; não substitui prova de unicidade C2.
        with patch.object(service, 'find_for_target', return_value=[row, row]):
            self.blocked('assignment_inconsistent')

    def test_invalid_ids_and_missing_tenant_fail_before_queries(self):
        for tenant, client, uc in ((None, 11, 101), (True, 11, 101),
                                   (10, '11', 101), (10, 0, 101), (10, 11, True),
                                   (10, 11, -1)):
            g.current_empresa_id = tenant
            with self.subTest(tenant=tenant, client=client, uc=uc):
                self.blocked('invalid_context', client=client, uc=uc)

    def test_revision_updated_by_c1_is_carried_on_next_resolution(self):
        from services.grupo_regra_cobranca_service import update_rule
        self.assign('company')
        self.assertEqual(self.resolve().rule_version, '3')
        update_rule(1, {'manualTariff': '0.654321'})
        result = self.resolve()
        self.assertEqual(result.rule_version, '4')
        self.assertEqual(result.manual_tariff, Decimal('0.654321'))

    def test_absent_values_and_documented_component_are_not_invented(self):
        self.assign('company')
        self.assign('consumer_unit', 3)
        group = GrupoRegraCobranca.query.filter_by(id=3, empresa_id=10).one()
        group.tariff_source, group.manual_tariff = 'invoice', None
        group.discount_type, group.discount_value = 'none', None
        group.monthly_interest = None
        group.tariff_basis, group.energy_component_index = 'documented_component', 7
        db.session.commit()
        result = self.resolve()
        for field in ('manual_tariff', 'discount_value', 'monthly_interest', 'fine_percentage'):
            self.assertIsNone(getattr(result, field))
        self.assertEqual(result.energy_component_index, 7)

    def test_read_only_and_exact_queries_have_bounded_cost(self):
        self.assign('company')
        before = {table.name: db.session.execute(table.select()).all()
                  for table in db.metadata.tables.values()}
        statements = []
        def record(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)
        event.listen(db.engine, 'before_cursor_execute', record)
        try:
            with patch.object(service, 'find_for_target', wraps=service.find_for_target) as lookup:
                self.resolve()
            self.assertEqual([call.args[0] for call in lookup.call_args_list],
                             ['consumer_unit', 'client', 'company'])
            self.assertEqual(lookup.call_args_list[0].kwargs, {'consumer_unit_id': 101, 'refresh': True})
            self.assertEqual(lookup.call_args_list[1].kwargs, {'client_id': 11, 'refresh': True})
        finally:
            event.remove(db.engine, 'before_cursor_execute', record)
        self.assertLessEqual(len(statements), 8)
        self.assertTrue(all(sql.lstrip().upper().startswith('SELECT') for sql in statements))
        for sql in statements:
            where = sql.partition('WHERE')[2]
            self.assertIn('empresa_id', where)
            self.assertNotIn('padrao', where)
        after = {table.name: db.session.execute(table.select()).all()
                 for table in db.metadata.tables.values()}
        self.assertEqual(before, after)
        self.assertFalse(db.session.new or db.session.dirty or db.session.deleted)

    def test_dirty_session_is_not_flushed_or_rolled_back(self):
        client = Client.query.filter_by(id=11, empresa_id=10).one()
        client.nome = 'Pendente'
        with patch.object(db.session, 'flush', side_effect=AssertionError('Não pode gravar')):
            self.blocked('invalid_context')
        self.assertEqual(client.nome, 'Pendente')
        self.assertIn(client, db.session.dirty)

    def test_existing_identity_map_does_not_hide_updated_rule_or_assignment(self):
        assignment = self.assign('company')
        group = GrupoRegraCobranca.query.filter_by(id=1, empresa_id=10).one()
        self.assertEqual(group.revision, 3)
        # Atualização persistida sem sincronizar os objetos já carregados.
        db.session.execute(db.update(GrupoRegraCobranca).where(
            GrupoRegraCobranca.empresa_id == 10, GrupoRegraCobranca.id == 1,
        ).values(revision=8).execution_options(synchronize_session=False))
        self.assertEqual(group.revision, 3)
        self.assertEqual(self.resolve().rule_version, '8')
        db.session.execute(db.update(RegraCobrancaAssignment).where(
            RegraCobrancaAssignment.empresa_id == 10,
            RegraCobrancaAssignment.id == assignment.id,
        ).values(grupo_regra_cobranca_id=2).execution_options(synchronize_session=False))
        self.assertEqual(assignment.grupo_regra_cobranca_id, 1)
        self.assertEqual(self.resolve().rule_id, 2)

    def test_technical_database_failure_remains_technical(self):
        with patch.object(service, 'find_for_target', side_effect=OperationalError('SELECT', {}, Exception())):
            with self.assertRaises(OperationalError):
                self.resolve()


if __name__ == '__main__':
    unittest.main()
