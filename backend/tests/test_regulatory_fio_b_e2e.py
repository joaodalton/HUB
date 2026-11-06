"""C5.4.4: prova opt-in contra a tarifa ANEEL realmente publicada."""
import os
import unittest
from dataclasses import replace
from decimal import Decimal

from app import create_app
from models.regulatory_tariff import RegulatoryTariff, RegulatoryTariffImport
from services.billing_calculation_contracts import BillingCalculationContext
from services.billing_calculation_engine import BillingCalculationEngine
from services.commercial_deduction_resolver import CommercialDeductionResolver
from services.fio_b_resolver import FioBResolver
from services.regulatory_tariff_repository import RegulatoryTariffRepository
from tests import test_billing_deductions
from tests.test_fio_b_resolver import invoice as fio_invoice
from tests.test_document_tariff_resolver import found


@unittest.skipUnless(os.getenv('RUN_LIVE_REGULATORY_E2E') == '1',
                     'requer RUN_LIVE_REGULATORY_E2E=1 e PostgreSQL publicado')
class RegulatoryFioBE2ETest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()

    def test_published_aneel_tariff_flows_to_final_billing_result(self):
        with self.app.app_context():
            imported = RegulatoryTariffImport.query.filter_by(id=1, status='completed').one()
            row = RegulatoryTariff.query.filter_by(
                import_id=imported.id, official_distributor='COPEL-DIS', component='TUSD_FIO_B',
                subgroup='B1', modality='CONVENCIONAL', tariff_class='Residencial',
                tariff_subclass='Residencial', tariff_detail='SCEE', tariff_period='',
            ).one()
            self.assertEqual((RegulatoryTariff.query.count(), imported.summary['created'], imported.summary['unchanged']),
                             (53, 53, 0))
            self.assertEqual(imported.summary['ckan']['resourceId'], 'e8717aa8-2521-453f-bf16-fbb9a16eea39')
            self.assertEqual((row.source_value, row.source_unit, row.value_kwh),
                             (Decimal('214.53560037400001'), 'R$/MWh', Decimal('0.21453560037400001')))
            self.assertEqual((row.valid_from.isoformat(), row.valid_until.isoformat(), row.source_version),
                             ('2026-06-24', '2027-06-23', '2026-09-17T15:31:25.510600'))

            records = tuple(RegulatoryTariffRepository().fio_b_tariffs())
            record = next(item for item in records if item.source_url == row.source_url and item.subgroup == 'B1'
                          and item.modality == 'CONVENCIONAL' and item.tariff_class == 'Residencial'
                          and item.tariff_subclass == 'Residencial')
            self.assertEqual((record.source, record.source_value, record.source_unit, record.unit_tariff,
                              record.valid_from, record.valid_to, record.version),
                             ('ANEEL', row.source_value, 'R$/MWh', row.source_value / Decimal(1000),
                              '2026-07', '2027-05', row.source_version))

            invoice = replace(fio_invoice(tariff=None), empresa_id=1, client_id=2, consumer_unit_id=4)
            invoice.campos.update({name: found(value) for name, value in (
                ('concessionaria', 'Copel'), ('subgrupo_tarifario', 'B1'),
                ('modalidade_tarifaria', 'CONVENCIONAL'), ('classe_tarifaria', 'Residencial'),
                ('subclasse_tarifaria', 'Residencial'))})
            fio_b = FioBResolver().resolve(invoice)[0]
            self.assertEqual((fio_b.status, fio_b.tariff_source, fio_b.energy_kwh, fio_b.transition_rate,
                              fio_b.tusd_fio_b_unit_tariff, fio_b.amount),
                             ('RESOLVED', 'REGULATORY', Decimal('1000'), Decimal('.60'), row.value_kwh,
                              Decimal('128.721360224400006000')))

            case = test_billing_deductions.BillingDeductionsTest(); case.setUp()
            rule = case.configured(pis=False)
            deductions = CommercialDeductionResolver().resolve(invoice=invoice, rule=rule)
            self.assertEqual((deductions.status, deductions.total_fio_b, deductions.fio_b_components[0].tariff_source),
                             ('VALID', fio_b.amount, 'REGULATORY'))
            result = BillingCalculationEngine().calculate(
                invoice=invoice, rule=rule, context=BillingCalculationContext(1, 2, 4, 3, '2026-09'))
            component = result.calculation_memory.fio_b_components[0]
            self.assertEqual((result.hub_amount, result.calculation_memory.fio_b_amount,
                              component['tariff_source'], Decimal(component['amount'])),
                             (Decimal('591.28'), fio_b.amount, 'REGULATORY', fio_b.amount))
            evidence = component['evidence'][0]
            self.assertEqual((evidence['source'], evidence['official_distributor'], evidence['component'],
                              evidence['source_value'], evidence['source_unit'], evidence['source_url'], evidence['version']),
                             ('ANEEL', 'COPEL-DIS', 'TUSD_FIO_B', str(row.source_value), 'R$/MWh',
                              row.source_url, row.source_version))
