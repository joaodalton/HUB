"""C5.5: execução financeira usa apenas extração Copel persistida e validada."""
import hashlib
import json
from copy import deepcopy
import sys
import tempfile
import unittest
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from flask import g

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from extensions import db
from models.client import Client
from models.consumer_unit import ConsumerUnit
from models.document import Document
from models.empresa import Empresa
from models.fatura_concessionaria import FaturaConcessionaria
from models.grupo_regra_cobranca import GrupoRegraCobranca
from models.regra_cobranca_assignment import RegraCobrancaAssignment
from models.calculo_cobranca import BillingCalculationExecution, BillingCalculationSnapshot
from services.invoice_normalization_service import InvoiceNormalizer, json_safe
from services.invoice_parsers.copel import CopelDANF3EParser
from services.invoice_parsers.schemas import ExtractedField

try:
    from .support import IsolatedTestRuntime
except ImportError:
    from support import IsolatedTestRuntime


FIXTURES = Path(__file__).parent / 'fixtures/invoices/copel'


class BillingCalculationServiceTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.prepare_test_runtime('sqlite:///' + (Path(cls.temp.name) / 'orchestration.db').as_posix(),
                                 'billing-orchestration-test', limiter_enabled=False)
        cls.app = create_app()

    @classmethod
    def tearDownClass(cls):
        cls.restore_test_runtime()
        cls.temp.cleanup()

    def setUp(self):
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        for tenant in (10, 20):
            db.session.add(Empresa(id=tenant, nome=f'Empresa {tenant}', slug=f'billing-{tenant}'))
            db.session.add(Client(id=tenant, empresa_id=tenant, nome='Cliente', cpf=str(tenant),
                                  email=f'{tenant}@example.test'))
            db.session.add(Document(id=tenant, empresa_id=tenant, client_id=tenant,
                                    nome='copel.pdf', storage_provider='google_drive'))
            db.session.add(ConsumerUnit(id=tenant, empresa_id=tenant, client_id=tenant,
                                        codigo='000000000000001'))
            db.session.add(FaturaConcessionaria(id=tenant, empresa_id=tenant, client_id=tenant,
                                                consumer_unit_id=tenant, document_id=tenant,
                                                arquivo_hash=hashlib.sha256((FIXTURES / 'core_anon.pdf').read_bytes()).hexdigest(),
                                                status_extracao='extraida', status_validacao='valida'))
            db.session.add(GrupoRegraCobranca(id=tenant, empresa_id=tenant, nome='Regra',
                ativo=True, padrao=False, revision=1, calculation_method='energia_compensada',
                tariff_source='invoice', manual_tariff=Decimal('0.70'), discount_type='none',
                tariff_basis='compensated', billing_mode='auto', due_date_basis='invoice_due_date',
                due_date_offset_days=0))
        db.session.commit()
        g.current_empresa_id = 10
        self.persist_normalized()
        db.session.add(RegraCobrancaAssignment(empresa_id=10, grupo_regra_cobranca_id=10,
                                               scope_type='company', ativo=True))
        db.session.commit()

    def tearDown(self):
        db.session.rollback()
        db.session.remove()
        g.pop('current_empresa_id', None)
        db.drop_all()
        db.engine.dispose()
        self.context.pop()

    def persist_normalized(self, *, gd=True, gd_unsupported=False):
        parser = CopelDANF3EParser()
        parsed = parser.parse((FIXTURES / 'core_anon.pdf').read_bytes())
        if gd:
            rows = json.loads((FIXTURES / 'gd_events_sanitized.json').read_text(encoding='utf-8'))['ouc_gdi_gdii_2026_09'][:2]
            if gd_unsupported:
                rows = [{**row, 'label': row['label'].replace('GDI-I', 'GDIII-III')}
                        for row in rows]
            def field(value):
                return ExtractedField('found', value, Decimal('0.95'), 'sanitized:copel-real')
            items = tuple({'descricao_original': field(row['label']), 'unidade': field('kWh'),
                           'quantidade': field(Decimal(row['quantity_kwh'])),
                           'tarifa_unitaria': field(Decimal(row['tariff_unit'])),
                           'preco_unitario_com_tributos': field(Decimal(row['taxed_unit_price']))}
                          for row in rows)
            components, _, _ = parser._energy(items, field(Decimal('0')))
            parsed = replace(parsed, itens=parsed.itens + items,
                             energy_components=parsed.energy_components + components,
                             compensation_supported=True)
        normalized = InvoiceNormalizer().normalize(parsed, empresa_id=10, client_id=10,
                                                   fatura_concessionaria_id=10)
        invoice = FaturaConcessionaria.query.filter_by(id=10).one()
        invoice.dados_normalizados = {'invoice': json_safe(replace(normalized, consumer_unit_id=10)),
                                     'validation': {'status': 'valida', 'consumer_unit_id': 10,
                                                    'uc_numero': '000000000000001', 'issues': []}}
        invoice.competencia = '2030-08'
        invoice.parser_name = normalized.identity.parser_name
        invoice.parser_version = normalized.identity.parser_version
        invoice.layout_name = normalized.identity.layout_name
        invoice.layout_version = normalized.identity.layout_version
        db.session.commit()

    def execute(self, identifier=10):
        from services.billing_calculation_service import BillingCalculationService
        return BillingCalculationService().execute(identifier)

    def test_sanitized_copel_calculates_one_te_tusd_volume_and_reuses_snapshot(self):
        first = self.execute()
        second = self.execute()
        self.assertEqual((first.status, second.status), ('CALCULATED', 'CALCULATED'), first.auditoria)
        self.assertEqual(first.snapshot_id, second.snapshot_id)
        self.assertEqual(BillingCalculationExecution.query.count(), 2)
        self.assertEqual(BillingCalculationSnapshot.query.count(), 1)
        self.assertEqual(first.snapshot.valor_final, Decimal('10.74'))
        self.assertEqual(first.snapshot.resultado['energia_compensada_kwh'], '30')
        self.assertGreaterEqual(Decimal(first.auditoria['duration_ms']), 0)
        self.assertEqual([step['stage'] for step in first.auditoria['stages']],
                         ['UPLOAD', 'EXTRACTION', 'NORMALIZATION', 'UC_MATCHING',
                          'RULE_RESOLUTION', 'TARIFF_RESOLUTION', 'ENERGY_RESOLUTION',
                          'COMMERCIAL_DEDUCTIONS', 'FIO_B', 'FINAL_CALCULATION', 'SNAPSHOT'])
        self.assertEqual([row['status'] for row in first.auditoria['stages'][:3]],
                         ['PERSISTED', 'PERSISTED', 'PERSISTED'])
        self.assertTrue(all('component' in row and 'version' in row and 'duration_ms' in row
                            for row in first.auditoria['stages']))
        measured = (3, 4, 5, 6, 9, 10)
        self.assertTrue(all(first.auditoria['stages'][index]['duration_ms'] is not None
                            and Decimal(first.auditoria['stages'][index]['duration_ms']) >= 0
                            for index in measured))
        self.assertIsNone(first.auditoria['stages'][7]['duration_ms'])
        self.assertIsNone(first.auditoria['stages'][8]['duration_ms'])

    def test_uc_discount_changes_only_new_snapshot(self):
        uc = ConsumerUnit.query.filter_by(id=10).one()
        group = GrupoRegraCobranca.query.filter_by(id=10).one()
        group.discount_type = 'percentage'
        group.discount_value = Decimal('30')
        uc.desconto = '20%'
        db.session.commit()
        discounted = self.execute()
        self.assertEqual(discounted.status, 'CALCULATED', discounted.auditoria)
        self.assertEqual(discounted.snapshot.valor_final, Decimal('8.59'))
        self.assertEqual(discounted.snapshot.regra_snapshot['discount_value'], '20')
        self.assertEqual(discounted.snapshot.regra_snapshot['metadata']['configured_discount_value'], '30.000000')
        self.assertEqual(discounted.snapshot.resultado['discount_amount'], '2.148138')
        original_id = discounted.snapshot_id

        uc.desconto = ''
        db.session.commit()
        without_discount = self.execute()
        self.assertEqual(without_discount.status, 'CALCULATED', without_discount.auditoria)
        self.assertNotEqual(without_discount.snapshot_id, original_id)
        self.assertEqual(without_discount.snapshot.valor_final, Decimal('10.74'))
        self.assertEqual(without_discount.snapshot.regra_snapshot['discount_type'], 'none')
        self.assertEqual(BillingCalculationSnapshot.query.filter_by(id=original_id).one().valor_final,
                         Decimal('8.59'))

    def test_invalid_uc_discount_blocks_without_snapshot(self):
        uc = ConsumerUnit.query.filter_by(id=10).one()
        for invalid in ('abc', 'NaN', '-1', '100.01'):
            uc.desconto = invalid
            db.session.commit()
            result = self.execute()
            self.assertEqual(result.status, 'REVIEW_REQUIRED', (invalid, result.auditoria))
            self.assertIsNone(result.snapshot_id)
            self.assertIn('UC_DISCOUNT_INVALID', result.auditoria['stages'][4]['blockers'])
        self.assertEqual(BillingCalculationSnapshot.query.count(), 0)

    def test_discount_uses_validated_tenant_uc(self):
        own = ConsumerUnit.query.filter_by(id=10).one()
        own.desconto = '20'
        g.current_empresa_id = 20
        foreign = ConsumerUnit.query.filter_by(id=20, empresa_id=20).one()
        foreign.desconto = '90'
        db.session.commit()
        g.current_empresa_id = 10
        result = self.execute()
        self.assertEqual(result.status, 'CALCULATED', result.auditoria)
        self.assertEqual(result.snapshot.valor_final, Decimal('8.59'))
        self.assertEqual(result.snapshot.regra_snapshot['discount_value'], '20')

    def test_specific_tariff_keeps_uc_discount_audited_without_applying_it(self):
        group = GrupoRegraCobranca.query.filter_by(id=10).one()
        group.calculation_method = 'tarifa_especifica'
        uc = ConsumerUnit.query.filter_by(id=10).one()
        uc.desconto = '20'
        db.session.commit()
        result = self.execute()
        self.assertEqual(result.status, 'CALCULATED', result.auditoria)
        self.assertEqual(result.snapshot.valor_final, Decimal('21.00'))
        self.assertEqual(result.snapshot.regra_snapshot['discount_value'], '20')
        self.assertEqual(result.snapshot.resultado['calculation_memory']['desconto_aplicado'], False)

    def test_foreign_invoice_is_not_resolved(self):
        with self.assertRaises(LookupError):
            self.execute(20)
        self.assertEqual(BillingCalculationExecution.query.count(), 0)

    def test_unvalidated_and_missing_uc_leave_durable_blockers_without_amount(self):
        invoice = FaturaConcessionaria.query.filter_by(id=10).one()
        invoice.status_validacao = 'uc_nao_encontrada'
        invoice.consumer_unit_id = None
        db.session.commit()
        execution = self.execute()
        self.assertEqual(execution.status, 'REVIEW_REQUIRED')
        self.assertIsNone(execution.snapshot_id)
        self.assertEqual(BillingCalculationSnapshot.query.count(), 0)

    def test_duplicate_uc_code_requires_review_even_if_prior_validation_was_valid(self):
        db.session.add(ConsumerUnit(id=11, empresa_id=10, client_id=10,
                                    codigo='000000000000001'))
        db.session.commit()
        execution = self.execute()
        self.assertEqual(execution.status, 'REVIEW_REQUIRED')
        self.assertIsNone(execution.snapshot_id)

    def test_unavailable_document_tariff_preserves_missing_state(self):
        invoice = FaturaConcessionaria.query.filter_by(id=10).one()
        payload = deepcopy(invoice.dados_normalizados)
        payload['invoice']['itens_documentais'][0]['tarifa_unitaria'].update(
            status='not_present', value=None)
        payload['invoice']['tariffs_documented'][0]['tarifa_unitaria'].update(
            status='not_present', value=None)
        invoice.dados_normalizados = payload
        db.session.commit()
        execution = self.execute()
        self.assertEqual(execution.status, 'MISSING_DATA', execution.auditoria)
        self.assertIsNone(execution.snapshot_id)

    def test_unsupported_gd_event_never_becomes_zero(self):
        self.persist_normalized(gd_unsupported=True)
        execution = self.execute()
        self.assertEqual(execution.status, 'UNSUPPORTED', execution.auditoria)
        self.assertIsNone(execution.snapshot_id)

    def test_missing_tax_link_is_reported_at_deduction_stage(self):
        rule = GrupoRegraCobranca.query.filter_by(id=10).one()
        rule.exclude_pis_cofins = True
        db.session.commit()
        execution = self.execute()
        self.assertEqual(execution.status, 'MISSING_DATA', execution.auditoria)
        self.assertEqual(execution.auditoria['stages'][7]['stage'], 'COMMERCIAL_DEDUCTIONS')
        self.assertEqual(execution.auditoria['stages'][7]['status'], 'MISSING_DATA')
        self.assertEqual(execution.auditoria['stages'][8]['status'], 'NOT_REACHED')
        self.assertIsNone(execution.snapshot_id)

    def test_reused_snapshot_must_belong_to_same_invoice(self):
        first = self.execute()
        self.assertEqual(first.status, 'CALCULATED')
        execution_id, snapshot_id = first.id, first.snapshot_id
        db.session.add(FaturaConcessionaria(id=11, empresa_id=10, client_id=10,
            consumer_unit_id=10, document_id=10, arquivo_hash='b' * 64))
        db.session.commit()
        db.session.expunge(first)
        db.session.execute(db.text('DELETE FROM billing_calculation_executions WHERE id = :id'),
                           {'id': execution_id})
        db.session.execute(db.text('UPDATE billing_calculation_snapshots '
            'SET fatura_concessionaria_id = 11 WHERE id = :id'), {'id': snapshot_id})
        db.session.commit()
        db.session.expire_all()
        again = self.execute()
        self.assertEqual(again.status, 'ERROR', again.auditoria)
        self.assertIsNone(again.snapshot_id)
        self.assertEqual(BillingCalculationSnapshot.query.count(), 1)

    def test_changed_engine_version_creates_new_snapshot(self):
        from services.billing_calculation_engine import BillingCalculationEngine

        first = self.execute()
        original = BillingCalculationEngine.calculate

        def upgraded(engine, **kwargs):
            result = original(engine, **kwargs)
            object.__setattr__(result, 'calculation_version', '2.0')
            return result

        with patch.object(BillingCalculationEngine, 'calculate', upgraded):
            second = self.execute()
        self.assertEqual((first.status, second.status), ('CALCULATED', 'CALCULATED'))
        self.assertNotEqual(first.snapshot_id, second.snapshot_id)
        self.assertEqual(BillingCalculationSnapshot.query.count(), 2)
        self.assertEqual(second.snapshot.resultado['calculation_version'], '2.0')

    def test_missing_rule_is_not_silently_defaulted(self):
        assignment = RegraCobrancaAssignment.query.one()
        assignment.ativo = False
        db.session.commit()
        execution = self.execute()
        self.assertEqual(execution.status, 'MISSING_DATA', execution.auditoria)
        self.assertIsNone(execution.snapshot_id)

    def test_real_copel_without_compensation_is_unsupported(self):
        self.persist_normalized(gd=False)
        execution = self.execute()
        self.assertEqual(execution.status, 'UNSUPPORTED', execution.auditoria)
        self.assertIsNone(execution.snapshot_id)

    def test_incomplete_persisted_contract_is_blocked(self):
        invoice = FaturaConcessionaria.query.filter_by(id=10).one()
        invoice.dados_normalizados = {'invoice': {'campos': {}}}
        db.session.commit()
        execution = self.execute()
        self.assertEqual(execution.status, 'MISSING_DATA')
        self.assertIsNone(execution.snapshot_id)

    def test_stale_validation_does_not_approve_missing_required_field(self):
        invoice = FaturaConcessionaria.query.filter_by(id=10).one()
        payload = deepcopy(invoice.dados_normalizados)
        payload['invoice']['campos']['consumo_kwh'].update(status='not_present', value=None)
        invoice.dados_normalizados = payload
        db.session.commit()
        execution = self.execute()
        self.assertEqual(execution.status, 'MISSING_DATA', execution.auditoria)
        self.assertIsNone(execution.snapshot_id)

    def test_parser_version_mismatch_is_review_required(self):
        invoice = FaturaConcessionaria.query.filter_by(id=10).one()
        payload = deepcopy(invoice.dados_normalizados)
        payload['invoice']['identity']['parser_version'] = 'untrusted'
        invoice.dados_normalizados = payload
        db.session.commit()
        execution = self.execute()
        self.assertEqual(execution.status, 'REVIEW_REQUIRED', execution.auditoria)
        self.assertIsNone(execution.snapshot_id)


if __name__ == '__main__':
    unittest.main()
