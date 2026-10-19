"""C5.3B: selecao comercial pura por evento tarifario documental."""
import ast
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.billing_calculation_contracts import BillingModifiers, ResolvedBillingRule
from services.commercial_tariff_selector import (
    CommercialTariffSelector, CommercialTariffSource, SelectedCommercialTariff,
)
from services.document_tariff_resolver import (
    DocumentTariffResolver, ResolvedDocumentTariffs, ResolutionStatus,
)
from services.invoice_normalization_service import json_safe
from tests.test_document_tariff_resolver import compensation_invoice, copel_invoice, found


EVENTS = (
    {'context': 'ouc', 'month': '2026-07', 'gd': 'GD_I', 'quantity': '-30',
     'te': '0.310850', 'tusd': '0.457170',
     'te_taxed': '0.310667', 'tusd_taxed': '0.457000'},
    {'context': 'ouc', 'month': '2026-08', 'gd': 'GD_II', 'quantity': '-352',
     'te': '0.310850', 'tusd': '0.328431',
     'te_taxed': '0.310824', 'tusd_taxed': '0.328409'},
)


def rule(method='energia_compensada', tariff='0.70', *, icms=None, flag=None,
         version='12', tariff_source='invoice'):
    return ResolvedBillingRule(
        rule_id=1, rule_name='C5.3B', rule_version=version,
        source_scope='company', source_id=1, calculation_method=method,
        tariff_source=tariff_source, discount_type='none',
        tariff_basis='compensated', billing_mode='auto',
        due_date_basis='invoice_due_date', due_date_offset_days=0,
        manual_tariff=None if tariff is None else Decimal(tariff),
        billing_modifiers=BillingModifiers(
            icms_policy=icms, exclude_tariff_flag=flag,
        ),
    )


def tariffs(events=EVENTS):
    resolver = DocumentTariffResolver()
    compensation = resolver.resolve(compensation_invoice(events, separate_flag=True))
    full_invoice = deepcopy(copel_invoice())
    full_invoice.tariffs_documented[0]['tarifa_unitaria'] = found(Decimal('0.310850'))
    full_invoice.tariffs_documented[1]['tarifa_unitaria'] = found(Decimal('0.457170'))
    full = resolver.resolve(full_invoice).full_tariff
    return ResolvedDocumentTariffs(
        full, compensation.compensation_tariff, ResolutionStatus.VALID,
        full.issues + compensation.issues, compensation.compensation_tariff_events,
    )


class CommercialTariffSelectorTest(unittest.TestCase):
    def setUp(self):
        self.selector = CommercialTariffSelector()
        self.tariffs = tariffs()

    def select(self, selected_rule, resolved=None):
        return self.selector.select(
            self.tariffs if resolved is None else resolved, selected_rule,
        )

    def test_configured_fixed_tariff_is_selected_for_each_event(self):
        selected = self.select(rule('tarifa_fixa', '0.70'))
        self.assertEqual(len(selected), 2)
        self.assertTrue(all(item.source_kind == CommercialTariffSource.CONFIGURED_FIXED
                            and item.selected_tariff == Decimal('0.70') for item in selected))
        self.assertEqual(selected[1].document_full_tariff, Decimal('0.768020'))
        self.assertEqual(selected[1].document_compensation_tariff, Decimal('0.639281'))

    def test_configured_specific_tariff_is_not_replaced_by_document(self):
        selected = self.select(rule('tarifa_especifica', '0.72'))
        self.assertTrue(all(item.source_kind == CommercialTariffSource.CONFIGURED_SPECIFIC
                            and item.selected_tariff == Decimal('0.72') for item in selected))

    def test_configured_tariff_blocks_when_flag_variant_is_required_but_unknown(self):
        for method in ('tarifa_fixa', 'tarifa_especifica'):
            for policy in (True, False, None):
                with self.subTest(method=method, policy=policy):
                    selected = self.select(rule(method, '0.70', flag=policy))[0]
                    expected = (ResolutionStatus.VALID if policy is None
                                else ResolutionStatus.MISSING)
                    self.assertEqual(selected.status, expected)
                    self.assertEqual(selected.selected_tariff is not None,
                                     expected == ResolutionStatus.VALID)
                    if policy is not None:
                        self.assertIn('tariff_flag_evidence_missing',
                                      {issue.code for issue in selected.issues})

    def test_document_full_tariff_is_selected_per_event_without_recalculation(self):
        selected = self.select(rule(icms=None, flag=True))
        self.assertEqual([item.selected_tariff for item in selected],
                         [Decimal('0.768020'), Decimal('0.768020')])
        self.assertTrue(all(item.source_kind == CommercialTariffSource.DOCUMENT_FULL
                            for item in selected))

    def test_document_compensation_tariffs_preserve_gdi_and_gdii(self):
        selected = self.select(rule(icms='exclude', flag=True))
        self.assertEqual([
            (item.event.identity.classificacao_gd, item.event.identity.quantidade_kwh,
             item.selected_tariff, item.source_kind)
            for item in selected
        ], [
            ('GD_I', Decimal('30'), Decimal('0.768020'),
             CommercialTariffSource.DOCUMENT_COMPENSATION),
            ('GD_II', Decimal('352'), Decimal('0.639281'),
             CommercialTariffSource.DOCUMENT_COMPENSATION),
        ])

    def test_multiple_events_never_create_mean_or_choose_one_event(self):
        selected = self.select(rule(icms='exclude', flag=True))
        self.assertEqual(len(selected), 2)
        self.assertEqual({item.selected_tariff for item in selected},
                         {Decimal('0.768020'), Decimal('0.639281')})
        self.assertNotIn(Decimal('0.649391921466'),
                         {item.selected_tariff for item in selected})

    def test_invalid_event_blocks_even_configured_tariff(self):
        event = replace(
            self.tariffs.compensation_tariff_events[0],
            te_tariff=None, tusd_tariff=None, combined_tariff=None,
            status=ResolutionStatus.AMBIGUOUS,
        )
        resolved = replace(self.tariffs, compensation_tariff_events=(event,))
        selected = self.select(rule('tarifa_fixa'), resolved)[0]
        self.assertEqual(selected.status, ResolutionStatus.AMBIGUOUS)
        self.assertIsNone(selected.selected_tariff)
        self.assertIs(selected.includes_flag, event.includes_flag)
        self.assertIs(selected.with_taxes, event.with_taxes)
        self.assertIn('invalid_compensation_tariff_event',
                      {issue.code for issue in selected.issues})

    def test_missing_compensation_tariff_never_falls_back_to_full(self):
        event = replace(
            self.tariffs.compensation_tariff_events[0],
            te_tariff=None, tusd_tariff=None, combined_tariff=None,
            status=ResolutionStatus.MISSING,
        )
        resolved = replace(self.tariffs, compensation_tariff_events=(event,))
        selected = self.select(rule(icms='exclude', flag=True), resolved)[0]
        self.assertEqual(selected.status, ResolutionStatus.MISSING)
        self.assertIsNone(selected.selected_tariff)
        self.assertEqual(selected.document_full_tariff, Decimal('0.768020'))

    def test_missing_full_tariff_never_falls_back_to_compensation(self):
        full = replace(
            self.tariffs.full_tariff, value=None, with_taxes=None,
            includes_flag=None, status=ResolutionStatus.MISSING,
        )
        selected = self.select(
            rule(icms=None), replace(self.tariffs, full_tariff=full),
        )[0]
        self.assertEqual(selected.status, ResolutionStatus.MISSING)
        self.assertIsNone(selected.selected_tariff)
        self.assertEqual(selected.document_compensation_tariff, Decimal('0.768020'))

    def test_flag_policy_is_tristate_and_unknown_evidence_blocks(self):
        event = self.tariffs.compensation_tariff_events[0]
        cases = (
            (True, False, ResolutionStatus.VALID),
            (True, True, ResolutionStatus.UNSUPPORTED),
            (True, None, ResolutionStatus.MISSING),
            (False, True, ResolutionStatus.VALID),
            (False, False, ResolutionStatus.UNSUPPORTED),
            (False, None, ResolutionStatus.MISSING),
            (None, None, ResolutionStatus.VALID),
        )
        for policy, documented, expected in cases:
            with self.subTest(policy=policy, documented=documented):
                resolved = replace(
                    self.tariffs,
                    compensation_tariff_events=(replace(event, includes_flag=documented),),
                )
                selected = self.select(
                    rule(icms='exclude', flag=policy), resolved,
                )[0]
                self.assertEqual(selected.status, expected)
                self.assertEqual(selected.selected_tariff is not None,
                                 expected == ResolutionStatus.VALID)

    def test_with_taxes_is_only_transported_and_never_changes_value(self):
        event = self.tariffs.compensation_tariff_events[1]
        for state in (True, False, None):
            with self.subTest(state=state):
                resolved = replace(
                    self.tariffs,
                    compensation_tariff_events=(replace(event, with_taxes=state),),
                )
                selected = self.select(
                    rule(icms='exclude', flag=None), resolved,
                )[0]
                self.assertEqual(selected.selected_tariff, Decimal('0.639281'))
                self.assertIs(selected.with_taxes, state)

    def test_gdii_selection_does_not_apply_fio_b_or_other_deduction(self):
        selected = self.select(rule(icms='exclude', flag=True))[1]
        self.assertEqual(selected.selected_tariff, selected.event.combined_tariff)
        self.assertEqual(selected.selected_tariff, Decimal('0.639281'))

    def test_decimal_is_preserved_and_float_is_rejected(self):
        selected = self.select(rule(icms='exclude', flag=True))[0]
        self.assertIsInstance(selected.selected_tariff, Decimal)
        self.assertEqual(selected.to_dict()['selected_tariff'], '0.768020')
        with self.assertRaises(ValueError):
            replace(selected, selected_tariff=0.768020)

    def test_snapshot_reconstructs_rule_source_tariff_and_event(self):
        selected = self.select(rule(icms='exclude', flag=True, version='27'))[1]
        payload = selected.to_dict()
        self.assertEqual(payload['rule_snapshot']['rule_version'], '27')
        self.assertEqual(payload['source_kind'], 'document_compensation')
        self.assertEqual(payload['selected_tariff'], '0.639281')
        self.assertEqual(payload['event']['identity']['classificacao_gd'], 'GD_II')
        self.assertEqual(payload['event']['identity']['quantidade_kwh'], '352')

    def test_selector_is_pure_and_has_no_runtime_dependencies(self):
        selected_rule = rule(icms='exclude', flag=True)
        before = json_safe((self.tariffs, selected_rule))
        self.select(selected_rule)
        self.assertEqual(json_safe((self.tariffs, selected_rule)), before)
        path = Path(__file__).resolve().parents[1] / 'services/commercial_tariff_selector.py'
        imports = {node.module for node in ast.walk(
            ast.parse(path.read_text(encoding='utf-8'))
        ) if isinstance(node, ast.ImportFrom)}
        self.assertFalse({'flask', 'sqlalchemy', 'services.billing_rule_resolver',
                          'services.billing_calculation_engine'} & imports)

    def test_unsupported_method_is_rejected_even_without_events(self):
        empty = replace(self.tariffs, compensation_tariff_events=())
        with self.assertRaises(ValueError):
            self.select(rule('economia_gerada'), empty)
        with self.assertRaises(ValueError):
            self.select(rule(tariff_source='manual'), empty)

    def test_contract_rejects_non_valid_value_and_invalid_issue_types(self):
        selected = self.select(rule(icms='exclude', flag=True))[0]
        with self.assertRaises(ValueError):
            replace(selected, status=ResolutionStatus.MISSING)
        with self.assertRaises(TypeError):
            replace(selected, issues=('not-an-issue',))
        self.assertIsInstance(selected, SelectedCommercialTariff)


if __name__ == '__main__':
    unittest.main()
