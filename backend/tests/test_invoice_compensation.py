"""C4.3: domínio sintético. Não comprova extração de GD em PDF Copel real."""
import ast
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal, localcontext
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.invoice_parsers.schemas import ExtractedField, ParsedInvoice, ParserIdentity
from services.invoice_normalization_service import InvoiceNormalizer, json_safe
from services.invoice_compensation import BillingEnergyInput, EnergyStatus


def found(value):
    return ExtractedField('found', value, source='synthetic:document', confidence=Decimal('0.95'))


def parsed(events=(('event-1', '2026-06', '-1000', '-1000'),), **changes):
    items, components = [], []
    for context, month, te, tusd in events:
        for kind, quantity in (('TE', te), ('TUSD', tusd)):
            index = len(items)
            items.append({'descricao_original': found('MESMO TEXTO SINTETICO'),
                          'quantidade': found(Decimal(quantity)), 'unidade': found('kWh'),
                          'tarifa_unitaria': found(Decimal('0.123456')), 'valor': found(Decimal('-123.45')),
                          'icms_valor': found(Decimal('10')), 'pis_cofins_valor': found(Decimal('20'))})
            components.append({'category': found('compensated'), 'unit': found('kWh'),
                'amount_kwh': found(Decimal(quantity)), 'item_index': found(index),
                'origin': found('OUC'), 'period': found('MPT'), 'credit_month': found(month),
                'compensation_context': found(context), 'tariff_component': found(kind)})
    return ParsedInvoice(ParserIdentity('synthetic-domain-only', '1'),
        identificacao_fiscal={'competencia': found('09/2026')}, itens=tuple(items),
        energy_components=tuple(components), compensation_supported=True, **changes)


class InvoiceCompensationTest(unittest.TestCase):
    def normalize(self, document):
        return InvoiceNormalizer().normalize(document, empresa_id=1, client_id=2, fatura_concessionaria_id=3)

    def test_te_tusd_once_and_original_sign_financial_metadata_preserved(self):
        original = parsed()
        before = json_safe(original)
        invoice = self.normalize(original)
        energy = invoice.billing_energy_input
        self.assertEqual(energy.require_valid(), Decimal('1000'))
        self.assertEqual(energy.status, EnergyStatus.VALID)
        self.assertEqual(energy.fatura_concessionaria_id, 3)
        event, = energy.compensacoes
        self.assertEqual(event.quantidade_kwh, Decimal('1000'))
        self.assertEqual([c.tipo for c in event.componentes], ['TE', 'TUSD'])
        self.assertEqual([c.quantidade_original_kwh for c in event.componentes], [Decimal('-1000')] * 2)
        self.assertEqual(event.componentes[0].tarifa_r_kwh.value, Decimal('0.123456'))
        self.assertEqual(event.componentes[0].valor_r.value, Decimal('-123.45'))
        self.assertEqual(event.componentes[0].documento['icms_valor'].value, Decimal('10'))
        self.assertEqual(event.classificacao_gd, 'UNKNOWN')
        self.assertEqual((event.mes_origem, energy.competencia), ('2026-06', '2026-09'))
        self.assertTrue(event.source)
        self.assertEqual(json_safe(original), before)

    def test_divergence_blocks_whole_input_including_other_valid_events(self):
        invoice = self.normalize(parsed((('bad', '2026-06', '1000', '950'), ('good', '2026-07', '400', '400'))))
        energy = invoice.billing_energy_input
        self.assertEqual(energy.status, 'AMBIGUOUS')
        self.assertIsNone(energy.energia_compensada_cobravel_kwh)
        self.assertIn('DIVERGENCIA_COMPONENTES_COMPENSACAO', {i.code for i in energy.issues})
        self.assertEqual(invoice.status_normalizacao, 'revisao_necessaria')
        with self.assertRaises(ValueError):
            energy.require_valid()

    def test_credit_month_and_context_prevent_text_or_quantity_deduplication(self):
        energy = self.normalize(parsed((('credit', '2026-06', '400', '400'),
                                        ('credit', '2026-07', '600', '600')))).billing_energy_input
        self.assertEqual(energy.require_valid(), Decimal('1000'))
        self.assertEqual(len(energy.compensacoes), 2)
        separate = self.normalize(parsed((('a', '2026-06', '400', '400'),
                                          ('b', '2026-06', '400', '400')))).billing_energy_input
        self.assertEqual(separate.require_valid(), Decimal('800'))
        self.assertEqual(len(separate.compensacoes), 2)

    def test_non_compensation_categories_balance_planning_taxes_never_add_energy(self):
        doc = parsed(energia={'saldo_creditos_kwh': found(Decimal('3500')),
                             'energia_rateada_esperada_kwh': found(Decimal('2000')),
                             'energia_injetada_kwh': found(Decimal('9999'))},
                     resumo={'consumo_kwh': found(Decimal('7777'))})
        for category in ('injected', 'consumed', 'credit_balance', 'expected_allocation', 'demand', 'availability', 'financial'):
            component = {'category': found(category), 'amount_kwh': found(Decimal('8888'))}
            invoice = self.normalize(replace(doc, energy_components=(*doc.energy_components, component)))
            self.assertEqual(invoice.billing_energy_input.require_valid(), Decimal('1000'))
            self.assertEqual(invoice.campos['saldo_credito_kwh'].value, Decimal('3500'))
        doc = deepcopy(doc)
        for item in doc.itens:
            for name in ('tarifa_unitaria', 'valor', 'icms_valor', 'pis_cofins_valor'):
                item[name] = found(Decimal('99999999'))
        self.assertEqual(self.normalize(doc).billing_energy_input.require_valid(), Decimal('1000'))

    def test_origins_periods_gd_are_metadata_not_multipliers(self):
        for origin, normalized_origin in (('MUC', 'MESMA_UC'), ('OUC', 'OUTRA_UC')):
            for period, normalized_period in (('MPT', 'MESMO_POSTO'), ('OPT', 'OUTRO_POSTO')):
                for gd in ('GD_I', 'GD_II', 'GD_III', 'UNKNOWN'):
                    doc = parsed()
                    for row in doc.energy_components:
                        row.update(origin=found(origin), period=found(period), gd_classification=found(gd))
                    energy = self.normalize(doc).billing_energy_input
                    self.assertEqual(energy.require_valid(), Decimal('1000'))
                    event, = energy.compensacoes
                    self.assertEqual((event.origem, event.posto, event.classificacao_gd), (normalized_origin, normalized_period, gd))

    def test_missing_unit_kw_and_missing_or_ambiguous_quantity_do_not_create_energy(self):
        for key, field in (('unit', found('kW')), ('unit', ExtractedField('not_present')),
                           ('amount_kwh', ExtractedField('failed')), ('amount_kwh', ExtractedField('ambiguous'))):
            doc = parsed()
            doc.energy_components[0][key] = field
            energy = self.normalize(doc).billing_energy_input
            self.assertIsNone(energy.energia_compensada_cobravel_kwh)
            with self.assertRaises(ValueError):
                energy.require_valid()

    def test_missing_context_duplicate_components_and_reused_lines_block(self):
        doc = parsed()
        del doc.energy_components[0]['compensation_context']
        self.assertEqual(self.normalize(doc).billing_energy_input.status, 'AMBIGUOUS')
        doc = parsed()
        duplicate = replace(doc, energy_components=(*doc.energy_components, doc.energy_components[0]))
        self.assertEqual(self.normalize(duplicate).billing_energy_input.status, 'AMBIGUOUS')
        doc.energy_components[1]['item_index'] = found(0)
        self.assertEqual(self.normalize(doc).billing_energy_input.status, 'AMBIGUOUS')
        only_te = replace(parsed(), energy_components=parsed().energy_components[:1])
        self.assertEqual(self.normalize(only_te).billing_energy_input.status, 'MISSING')

    def test_absent_month_is_not_replaced_by_invoice_month(self):
        doc = parsed()
        for row in doc.energy_components:
            del row['credit_month']
        energy = self.normalize(doc).billing_energy_input
        self.assertIsNone(energy.compensacoes[0].mes_origem)
        self.assertEqual(energy.competencia, '2026-09')

    def test_decimal_precision_and_explicit_zero(self):
        value = '0.12345678901234567890123456789'
        with localcontext() as context:
            context.prec = 6
            energy = self.normalize(parsed((('a', '2026-06', '-' + value, '-' + value),
                                             ('b', '2026-07', value, value)))).billing_energy_input
        self.assertEqual(energy.require_valid(), Decimal('0.24691357802469135780246913578'))
        self.assertIsInstance(energy.require_valid(), Decimal)
        self.assertEqual(self.normalize(parsed((('a', '2026-06', '0', '0'),))).billing_energy_input.require_valid(), Decimal('0'))
        self.assertEqual(json_safe(energy)['energia_compensada_cobravel_kwh'], '0.24691357802469135780246913578')

    def test_no_events_is_missing_current_copel_is_unsupported_not_fake_gd(self):
        self.assertEqual(self.normalize(parsed(())).billing_energy_input.status, 'MISSING')
        from services.invoice_parsers.copel import CopelDANF3EParser
        doc = CopelDANF3EParser().parse((Path(__file__).parent / 'fixtures/invoices/copel/core_anon.pdf').read_bytes())
        energy = self.normalize(doc).billing_energy_input
        self.assertEqual(energy.status, 'UNSUPPORTED')
        self.assertIsNone(energy.energia_compensada_cobravel_kwh)
        self.assertEqual(energy.compensacoes, ())

    def test_engine_contract_does_not_read_copel_labels(self):
        from services.billing_calculation_contracts import BillingCalculationEngine
        with self.assertRaises(TypeError):
            BillingCalculationEngine()
        code = (Path(__file__).resolve().parents[1] / 'services/billing_calculation_contracts.py').read_text(encoding='utf-8')
        self.assertNotIn('ENERGIA INJ', code)
        self.assertFalse(any(isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant)
                             and node.slice.value in ('descricao_original', 'descricao_normalizada')
                             for node in ast.walk(ast.parse(code))))
        energy = self.normalize(parsed()).billing_energy_input
        with self.assertRaises(ValueError):
            replace(energy, energia_compensada_cobravel_kwh=Decimal('2000'))
        with self.assertRaises(ValueError):
            replace(energy, status='MISSING')


if __name__ == '__main__':
    unittest.main()
