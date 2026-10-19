from copy import deepcopy
from decimal import Decimal, ROUND_DOWN, localcontext
import json
import unittest
from unittest.mock import patch

from services import regulatory_tariff_repository
from services.regulatory_tariff_repository import RegulatoryTariffRepository


class RegulatoryTariffRepositoryTest(unittest.TestCase):
    def test_copel_aneel_record_keeps_source_value_vigency_and_version(self):
        tariffs = tuple(RegulatoryTariffRepository().fio_b_tariffs())
        self.assertEqual(len(tariffs), 1)
        tariff = tariffs[0]
        self.assertEqual(tariff.distributor, 'Copel')
        self.assertEqual(tariff.component, 'TUSD_FIO_B')
        self.assertEqual(tariff.unit_tariff, Decimal('0.21453560037400001'))
        self.assertEqual((tariff.source_value, tariff.source_unit),
                         (Decimal('214.53560037400001'), 'R$/MWh'))
        self.assertEqual((tariff.valid_from_date, tariff.valid_until_date),
                         ('2026-06-24', '2027-06-23'))
        self.assertEqual((tariff.valid_from, tariff.valid_to), ('2026-07', '2027-05'))
        self.assertEqual(tariff.reference, 'RESOLUÇÃO HOMOLOGATÓRIA Nº 3.592, DE 23 DE JUNHO DE 2026')
        self.assertIn('e8717aa8-2521-453f-bf16-fbb9a16eea39', tariff.version)
        self.assertIn('de29320948667c675a0d8dc92fa176a4', tariff.version)

    def test_import_accepts_only_application_scee_and_is_decimal_context_independent(self):
        payload = json.loads(regulatory_tariff_repository._DATA.read_text(encoding='utf-8'))
        with localcontext() as context:
            context.prec, context.rounding = 2, ROUND_DOWN
            self.assertEqual(tuple(RegulatoryTariffRepository().fio_b_tariffs())[0].unit_tariff,
                             Decimal('0.21453560037400001'))
        for field in ('base_tariff', 'tariff_detail'):
            invalid = deepcopy(payload)
            invalid['tariffs'][0][field] = 'não aplicável'
            with patch.object(regulatory_tariff_repository.json, 'loads', return_value=invalid):
                self.assertEqual(tuple(RegulatoryTariffRepository().fio_b_tariffs()), ())


if __name__ == '__main__':
    unittest.main()
