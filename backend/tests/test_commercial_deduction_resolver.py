"""Fixtures estruturais sinteticas: nao comprovam deducoes nos PDFs reais."""
from dataclasses import replace
from decimal import Decimal, localcontext
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.billing_calculation_contracts import BillingModifiers
from services.commercial_deduction_resolver import (
    CommercialDeductionResolver, DocumentDeductionEvidence, EnergyStatus,
)
from services.invoice_parsers.schemas import ExtractedField, ExtractionIssue
from tests.test_commercial_tariff_selector import EVENTS, rule
from tests.test_document_tariff_resolver import compensation_invoice, found


def deduction_invoice():
    invoice = compensation_invoice(EVENTS)
    return replace(invoice, billing_energy_input=replace(invoice.billing_energy_input,
        fatura_concessionaria_id=7, competencia='2026-09'))


def deduction_rule(pis=None, fio=None):
    return replace(rule(), billing_modifiers=BillingModifiers(
        exclude_pis_cofins=pis, exclude_gdii_fio_b=fio))


def tax_row(kind, event, field):
    row = {'tributo': found(kind), 'valor': field, 'base_calculo': found(Decimal('100')),
           'aliquota': found(Decimal('0.91')), 'origin': found('OUC'), 'period': found('MPT'),
           'gd_classification': found(event.classificacao_gd),
           'compensation_context': found(event.contexto_documental)}
    if event.mes_origem is not None:
        row['credit_month'] = found(event.mes_origem)
    return row


def with_evidence(invoice, kind, value='10', event_index=1, field=None):
    field = found(Decimal(value)) if field is None else field
    index = len(invoice.itens_documentais)
    event = invoice.billing_energy_input.compensacoes[event_index]
    invoice = replace(invoice, itens_documentais=invoice.itens_documentais + (tax_row(kind, event, field),))
    evidence = DocumentDeductionEvidence(kind, event,
        field, (index,), f'itens_documentais[{index}].valor', 7, '2026-09')
    return invoice, evidence


class CommercialDeductionResolverTest(unittest.TestCase):
    def resolve(self, invoice=None, evidence=(), pis=None, fio=None):
        return CommercialDeductionResolver().resolve(invoice=invoice or deduction_invoice(),
            rule=deduction_rule(pis, fio), evidence=evidence)

    def test_disabled_deductions_are_legitimate_zero(self):
        for flag in (False, None):
            result = self.resolve(pis=flag, fio=flag)
            self.assertEqual(result.status, EnergyStatus.VALID)
            self.assertEqual(result.total_pis_cofins, Decimal(0))
            self.assertEqual(result.total_fio_b, Decimal(0))

    def test_enabled_pis_cofins_without_event_evidence_blocks(self):
        result = self.resolve(pis=True)
        self.assertEqual(result.status, EnergyStatus.MISSING)
        self.assertIsNone(result.total_pis_cofins)

    def test_aggregate_invoice_taxes_never_supply_compensation_deductions(self):
        invoice = replace(deduction_invoice(), tributos=({'PIS': found(Decimal('30')),
            'COFINS': found(Decimal('100')), 'base': found(Decimal('900'))},))
        self.assertIsNone(self.resolve(invoice, pis=True).total_pis_cofins)

    def test_pis_cofins_preserve_each_event_and_exact_totals(self):
        invoice, evidence = deduction_invoice(), []
        for index in (0, 1):
            for kind, value in (('PIS', '1.123456789123456789'), ('COFINS', '2.000000000000000001')):
                invoice, item = with_evidence(invoice, kind, value, index)
                evidence.append(item)
        with localcontext() as context:
            context.prec = 4
            result = self.resolve(invoice, evidence, pis=True)
            self.assertEqual(result.total_pis_cofins, Decimal('6.246913578246913580'))
        self.assertEqual(len(result.deductions), 4)
        self.assertEqual(result.deductions[0].applies_to_event.classificacao_gd, 'GD_I')

    def test_duplicate_candidates_are_ambiguous(self):
        invoice, item = with_evidence(deduction_invoice(), 'PIS')
        result = self.resolve(invoice, (item, item), pis=True)
        self.assertEqual(result.status, EnergyStatus.AMBIGUOUS)
        self.assertIsNone(result.total_pis)

    def test_same_monetary_source_cannot_supply_two_deduction_kinds(self):
        invoice, item = with_evidence(deduction_invoice(), 'PIS')
        duplicate = replace(item, kind='COFINS')
        result = self.resolve(invoice, (item, duplicate), pis=True, fio=True)
        self.assertEqual(result.status, EnergyStatus.AMBIGUOUS)
        self.assertIsNone(result.total_fio_b)
        self.assertIsNone(result.total_pis)

    def test_resolved_amount_cannot_diverge_from_its_evidence(self):
        invoice, item = with_evidence(deduction_invoice(), 'PIS', event_index=0)
        deduction = self.resolve(invoice, (item,), pis=True).deductions[0]
        with self.assertRaises(ValueError):
            replace(deduction, amount=Decimal('999'))

    def test_gdii_and_tusd_difference_do_not_create_fio_b(self):
        result = self.resolve(fio=True)
        self.assertEqual(result.status, EnergyStatus.MISSING)
        self.assertIsNone(result.total_fio_b)

    def test_legacy_monetary_fio_b_cannot_bypass_required_tariff(self):
        invoice, item = with_evidence(deduction_invoice(), 'PIS', '50.123456')
        result = self.resolve(invoice, (item,), fio=True)
        self.assertIsNone(result.total_fio_b)
        self.assertEqual(result.fio_b_components[1].status, 'MISSING_DATA')

    def test_foreign_invoice_and_month_evidence_block(self):
        invoice, item = with_evidence(deduction_invoice(), 'PIS', event_index=0)
        for foreign in (replace(item, fatura_concessionaria_id=8), replace(item, competencia='2026-08')):
            self.assertEqual(self.resolve(invoice, (foreign,), pis=True).deductions[0].status, EnergyStatus.MISSING)

    def test_foreign_event_does_not_supply_deduction(self):
        invoice, item = with_evidence(deduction_invoice(), 'PIS', event_index=0)
        foreign = replace(item, event=replace(item.event, contexto_documental='foreign'))
        self.assertEqual(self.resolve(invoice, (foreign,), pis=True).deductions[0].status, EnergyStatus.MISSING)

    def test_amount_not_in_document_is_blocked(self):
        invoice, item = with_evidence(deduction_invoice(), 'PIS', event_index=0)
        item = replace(item, amount=found(Decimal('999')))
        self.assertEqual(self.resolve(invoice, (item,), pis=True).deductions[0].status, EnergyStatus.MISSING)

    def test_incomplete_or_negative_evidence_blocks(self):
        for field in (found(Decimal('-1')), ExtractedField('not_present'),
                      ExtractedField('found', Decimal(1), Decimal('.9'))):
            invoice, item = with_evidence(deduction_invoice(), 'PIS', field=field, event_index=0)
            self.assertEqual(self.resolve(invoice, (item,), pis=True).deductions[0].status, EnergyStatus.MISSING)

    def test_unknown_confidence_is_preserved(self):
        invoice, item = with_evidence(deduction_invoice(), 'PIS', event_index=0,
            field=ExtractedField('found', Decimal(1), source='document'))
        result = self.resolve(invoice, (item,), pis=True)
        self.assertEqual(result.deductions[0].status, EnergyStatus.VALID)
        self.assertIsNone(result.deductions[0].confidence)

    def test_unit_tariff_cannot_be_referenced_as_monetary_amount(self):
        invoice, item = with_evidence(deduction_invoice(), 'PIS', event_index=0)
        item = replace(item, source_item_indexes=(0,), document_reference='itens_documentais[0].tarifa_unitaria',
            amount=invoice.itens_documentais[0]['tarifa_unitaria'])
        self.assertEqual(self.resolve(invoice, (item,), pis=True).deductions[0].status, EnergyStatus.MISSING)

    def test_documental_zero_is_valid(self):
        invoice, item = with_evidence(deduction_invoice(), 'PIS', '0', event_index=0)
        result = self.resolve(invoice, (item,), pis=True)
        self.assertEqual(result.deductions[0].status, EnergyStatus.VALID)
        self.assertEqual(result.deductions[0].amount, Decimal(0))

    def test_warning_confidence_and_source_remain_auditable(self):
        warning = ExtractionIssue('LOW_CONFIDENCE', 'warning', 'Revisar fonte.')
        field = found(Decimal('10'), Decimal('.6'), (warning,))
        invoice, item = with_evidence(deduction_invoice(), 'PIS', field=field, event_index=0)
        result = self.resolve(invoice, (item,), pis=True)
        self.assertEqual(result.deductions[0].confidence, Decimal('.6'))
        self.assertEqual(result.deductions[0].evidence[0].amount.warnings, (warning,))
        self.assertEqual(result.to_dict()['deductions'][0]['source_item_indexes'], list(item.source_item_indexes))

    def test_no_float_or_unlinked_evidence_contract(self):
        with self.assertRaises(TypeError):
            ExtractedField('found', 1.5)
        invoice, item = with_evidence(deduction_invoice(), 'PIS')
        with self.assertRaises(ValueError):
            replace(item, source_item_indexes=())
        with self.assertRaises(ValueError):
            replace(item, document_reference='')

    def test_amount_only_item_cannot_prove_documentary_tax_deduction(self):
        invoice, item = with_evidence(deduction_invoice(), 'PIS', event_index=0)
        invoice.itens_documentais[-1].clear()
        invoice.itens_documentais[-1]['valor'] = item.amount
        result = self.resolve(invoice, (item,), pis=True)
        self.assertEqual(result.deductions[0].status, EnergyStatus.MISSING)
        self.assertIsNone(result.deductions[0].amount)

    def test_legacy_fio_b_kind_is_not_a_monetary_evidence_contract(self):
        with self.assertRaises(ValueError):
            with_evidence(deduction_invoice(), 'GDII_FIO_B')

    def test_tax_kind_base_rate_and_event_identity_must_be_documented(self):
        for name in ('tributo', 'base_calculo', 'aliquota', 'origin', 'period',
                     'gd_classification', 'credit_month', 'compensation_context'):
            with self.subTest(field=name):
                invoice, item = with_evidence(deduction_invoice(), 'PIS', event_index=0)
                invoice.itens_documentais[-1].pop(name)
                self.assertEqual(self.resolve(invoice, (item,), pis=True).deductions[0].status, EnergyStatus.MISSING)
        invoice, item = with_evidence(deduction_invoice(), 'PIS', event_index=0)
        invoice.itens_documentais[-1]['tributo'] = found('COFINS')
        self.assertEqual(self.resolve(invoice, (item,), pis=True).deductions[0].status, EnergyStatus.MISSING)
