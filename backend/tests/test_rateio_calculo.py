"""Suite de calculo do rateio: aritmetica pura (rateio_math) e regras do
servico (confirmar_selecao, atualizar_distribuicao, aplicar_rateio, preview).
Antes desta suite o motor de rateio nao tinha nenhum teste de calculo."""
import os
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

_DATABASE_FILE = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_DATABASE_FILE.close()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flask import g  # noqa: E402

from app import create_app  # noqa: E402
from extensions import db  # noqa: E402
from models.client import Client  # noqa: E402
from models.consumer_unit import ConsumerUnit, PlantConnection  # noqa: E402
from models.empresa import Empresa  # noqa: E402
from models.plant import Plant  # noqa: E402
from models.rateio_historico import RateioHistorico  # noqa: E402
from services import rateio_math as rm  # noqa: E402
from services import rateio_service  # noqa: E402
try:
    from .support import IsolatedTestRuntime  # noqa: E402
except ImportError:
    from support import IsolatedTestRuntime  # noqa: E402


class RateioMathTest(unittest.TestCase):
    def test_half_up_rounding_matches_billing_policy(self):
        # float/round() nativo dava 2.67 (half-even); cobranca usa HALF_UP -> 2.68
        self.assertEqual(rm.q2(Decimal('2.675')), Decimal('2.68'))
        self.assertEqual(rm.validar_percentual('2.675'), Decimal('2.68'))
        self.assertEqual(rm.validar_percentual(2.675), Decimal('2.68'))

    def test_float_input_does_not_carry_binary_noise(self):
        self.assertEqual(rm.to_decimal(0.1) + rm.to_decimal(0.2), Decimal('0.3'))
        self.assertEqual(rm.soma_percentuais([0.1, 0.2, 0.3]), Decimal('0.60'))

    def test_validar_percentual_bounds_and_types(self):
        self.assertEqual(rm.validar_percentual(0), Decimal('0.00'))
        self.assertEqual(rm.validar_percentual('100'), Decimal('100.00'))
        for invalid in (-0.01, '100.01', 'abc', None, True, 'NaN', 'Infinity'):
            with self.assertRaises(ValueError, msg=repr(invalid)):
                rm.validar_percentual(invalid)

    def test_producao_disponivel_applies_reserve(self):
        self.assertEqual(rm.producao_disponivel('1000', '15'), Decimal('850.00'))
        self.assertEqual(rm.producao_disponivel('1000', 0), Decimal('1000.00'))
        self.assertEqual(rm.producao_disponivel(None, None), Decimal('0.00'))
        self.assertEqual(rm.producao_disponivel('333.333', '33.33'), Decimal('222.23'))

    def test_percentual_sugerido_chain(self):
        # consumo 500 kWh, 2 usinas -> 250; buffer 15% -> 287.50; producao 1000 -> 28.75%
        considerado, ajustado, pct = rm.percentual_sugerido('500', 2, '15', '1000')
        self.assertEqual((considerado, ajustado, pct), (Decimal('250.00'), Decimal('287.50'), Decimal('28.75')))

    def test_percentual_sugerido_without_production_is_zero(self):
        self.assertEqual(rm.percentual_sugerido('500', 1, 0, 0)[2], rm.ZERO)
        self.assertEqual(rm.percentual_sugerido('500', 1, 0, None)[2], rm.ZERO)

    def test_n_usinas_zero_is_treated_as_one(self):
        self.assertEqual(rm.consumo_considerado('300', 0), Decimal('300.00'))

    def test_sum_exactly_100_is_allowed_and_above_is_not(self):
        self.assertFalse(rm.excede_limite(rm.soma_percentuais(['33.33', '33.33', '33.34'])))
        self.assertTrue(rm.excede_limite(rm.soma_percentuais(['33.34', '33.33', '33.34'])))
        # 70 + 30.004 soma 100.00 apos quantize -> permitido; 70 + 30.005 -> 100.01
        self.assertFalse(rm.excede_limite(rm.soma_percentuais(['70', '30.004'])))
        self.assertTrue(rm.excede_limite(rm.soma_percentuais(['70', '30.005'])))

    def test_producao_considerada(self):
        self.assertEqual(rm.producao_considerada('28.75', '1000'), Decimal('287.50'))
        self.assertEqual(rm.producao_considerada('28.75', 0), rm.ZERO)


class RateioServiceTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepare_test_runtime(
            f"sqlite:///{_DATABASE_FILE.name.replace(chr(92), '/')}",
            'rateio-calculo-test-secret',
        )
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        with cls.app.app_context():
            db.create_all()
            db.session.add(Empresa(nome='A', slug='rateio-a'))
            db.session.commit()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        os.unlink(_DATABASE_FILE.name)
        cls.restore_test_runtime()

    def setUp(self):
        self.ctx = self.app.app_context()
        self.ctx.push()
        g.current_empresa_id = 1
        for model in (RateioHistorico, PlantConnection, ConsumerUnit, Client, Plant):
            db.session.query(model).delete()
        db.session.commit()
        self.client = Client(empresa_id=1, nome='Cliente', cpf='12345678900', email='c@x.test')
        self.plant = Plant(empresa_id=1, nome='Usina', uc='UC-P', kw_pico=100, producao_media_manual=Decimal('1000'), reserva_percentual=Decimal('10'))
        db.session.add_all([self.client, self.plant])
        db.session.flush()
        self.uc1 = ConsumerUnit(empresa_id=1, client_id=self.client.id, codigo='UC-1', consumo=Decimal('450'))
        self.uc2 = ConsumerUnit(empresa_id=1, client_id=self.client.id, codigo='UC-2', consumo=Decimal('270'))
        db.session.add_all([self.uc1, self.uc2])
        db.session.commit()

    def tearDown(self):
        db.session.rollback()
        self.ctx.pop()

    def test_preview_uses_decimal_half_up_and_sums_allocation(self):
        db.session.add_all([
            PlantConnection(empresa_id=1, plant_id=self.plant.id, consumer_unit_id=self.uc1.id, percentual=0),
            PlantConnection(empresa_id=1, plant_id=self.plant.id, consumer_unit_id=self.uc2.id, percentual=0),
        ])
        db.session.commit()
        [resultado] = rateio_service.preview_rateio(self.plant.id)
        self.assertEqual(resultado['producaoDisponivel'], 900.0)      # 1000 * (1 - 10%)
        por_uc = {u['ucCodigo']: u for u in resultado['ucs']}
        self.assertEqual(por_uc['UC-1']['percentualCalculado'], 50.0)  # 450 / 900
        self.assertEqual(por_uc['UC-2']['percentualCalculado'], 30.0)  # 270 / 900
        self.assertEqual(resultado['percentualTotalAlocado'], 80.0)
        self.assertFalse(resultado['excedeLimite'])

    def test_uc_in_two_plants_splits_consumption_equally(self):
        outra = Plant(empresa_id=1, nome='Usina 2', uc='UC-P2', kw_pico=50, producao_media_manual=Decimal('500'))
        db.session.add(outra)
        db.session.flush()
        db.session.add_all([
            PlantConnection(empresa_id=1, plant_id=self.plant.id, consumer_unit_id=self.uc1.id, percentual=0),
            PlantConnection(empresa_id=1, plant_id=outra.id, consumer_unit_id=self.uc1.id, percentual=0),
        ])
        db.session.commit()
        [resultado] = rateio_service.preview_rateio(self.plant.id)
        uc = resultado['ucs'][0]
        self.assertEqual(uc['consumoConsiderado'], 225.0)             # 450 / 2 usinas
        self.assertEqual(uc['percentualCalculado'], 25.0)             # 225 / 900

    def test_funil_simulates_extra_plant_and_applies_global_buffer(self):
        from services.settings_service import update_settings
        update_settings({'rateioBufferHabilitado': 'true', 'rateioBufferPercentual': '15'})
        funil = rateio_service.funil_qualificacao(self.plant.id)
        por_uc = {u['ucCodigo']: u for u in funil['ucs']}
        # 450 / 1 usina * 1.15 = 517.50 / 900 = 57.50%
        self.assertEqual(por_uc['UC-1']['percentualSugerido'], 57.5)
        self.assertEqual(por_uc['UC-2']['percentualSugerido'], 34.5)
        update_settings({'rateioBufferHabilitado': 'false'})

    def test_confirmar_selecao_rejects_sum_above_100_and_persists_nothing(self):
        with self.assertRaises(ValueError) as ctx:
            rateio_service.confirmar_selecao(self.plant.id, '2026-10', [
                {'ucId': self.uc1.id, 'percentual': '60'},
                {'ucId': self.uc2.id, 'percentual': 40.005},
            ])
        self.assertIn('100.01%', str(ctx.exception))
        self.assertEqual(PlantConnection.query.count(), 0)
        self.assertEqual(RateioHistorico.query.count(), 0)

    def test_confirmar_selecao_persists_decimal_and_history(self):
        resultado = rateio_service.confirmar_selecao(self.plant.id, '2026-10', [
            {'ucId': self.uc1.id, 'percentual': 2.675},
            {'ucId': self.uc2.id, 'percentual': '97.32'},  # 2.68 + 97.32 = 100.00
        ])
        self.assertEqual(resultado['conexoesCriadas'], 2)
        conexao = PlantConnection.query.filter_by(consumer_unit_id=self.uc1.id).one()
        self.assertEqual(Decimal(str(conexao.percentual)), Decimal('2.68'))
        self.assertTrue(conexao.percentual_manual)
        historico = RateioHistorico.query.filter_by(consumer_unit_id=self.uc1.id).one()
        self.assertEqual(Decimal(str(historico.producao_considerada)), Decimal('24.12'))  # 2.68% de 900
        self.assertEqual(Decimal(str(historico.consumo_considerado)), Decimal('450'))

    def test_confirmar_selecao_rejects_invalid_values(self):
        for percentual in ('abc', -1, 100.01, None):
            with self.assertRaises(ValueError, msg=repr(percentual)):
                rateio_service.confirmar_selecao(self.plant.id, '2026-10', [{'ucId': self.uc1.id, 'percentual': percentual}])

    def test_atualizar_distribuicao_counts_untouched_connections(self):
        c1 = PlantConnection(empresa_id=1, plant_id=self.plant.id, consumer_unit_id=self.uc1.id, percentual=Decimal('60'))
        c2 = PlantConnection(empresa_id=1, plant_id=self.plant.id, consumer_unit_id=self.uc2.id, percentual=Decimal('30'))
        db.session.add_all([c1, c2])
        db.session.commit()
        with self.assertRaises(ValueError):
            rateio_service.atualizar_distribuicao(self.plant.id, [{'connectionId': c1.id, 'percentual': '70.01'}])
        resultado = rateio_service.atualizar_distribuicao(self.plant.id, [{'connectionId': c1.id, 'percentual': '70'}])
        self.assertEqual({c['percentual'] for c in resultado['conexoes']}, {70.0, 30.0})
        self.assertTrue(PlantConnection.query.get(c1.id).percentual_manual)

    def test_aplicar_rateio_respects_manual_and_writes_history(self):
        manual = PlantConnection(empresa_id=1, plant_id=self.plant.id, consumer_unit_id=self.uc1.id, percentual=Decimal('12.34'), percentual_manual=True)
        auto = PlantConnection(empresa_id=1, plant_id=self.plant.id, consumer_unit_id=self.uc2.id, percentual=Decimal('0'))
        db.session.add_all([manual, auto])
        db.session.commit()
        rateio_service.aplicar_rateio('2026-10', self.plant.id)
        self.assertEqual(Decimal(str(PlantConnection.query.get(manual.id).percentual)), Decimal('12.34'))
        self.assertEqual(Decimal(str(PlantConnection.query.get(auto.id).percentual)), Decimal('30.00'))
        historico = {h.consumer_unit_id: h for h in RateioHistorico.query.filter_by(competencia='2026-10').all()}
        self.assertTrue(historico[self.uc1.id].manual)
        self.assertFalse(historico[self.uc2.id].manual)
        self.assertEqual(Decimal(str(historico[self.uc2.id].percentual)), Decimal('30.00'))

    def test_aplicar_rateio_rejects_sum_above_100_and_persists_nothing(self):
        # producaoDisponivel=900; uc1=450(50%) + uc2=270(30%) + uc3=300(33.33%) = 113.33%
        uc3 = ConsumerUnit(empresa_id=1, client_id=self.client.id, codigo='UC-3', consumo=Decimal('300'))
        db.session.add(uc3)
        db.session.flush()
        c1 = PlantConnection(empresa_id=1, plant_id=self.plant.id, consumer_unit_id=self.uc1.id, percentual=Decimal('0'))
        c2 = PlantConnection(empresa_id=1, plant_id=self.plant.id, consumer_unit_id=self.uc2.id, percentual=Decimal('0'))
        c3 = PlantConnection(empresa_id=1, plant_id=self.plant.id, consumer_unit_id=uc3.id, percentual=Decimal('0'))
        db.session.add_all([c1, c2, c3])
        db.session.commit()

        with self.assertRaises(ValueError) as ctx:
            rateio_service.aplicar_rateio('2026-10', self.plant.id)
        self.assertIn('excede 100%', str(ctx.exception))
        self.assertEqual(Decimal(str(PlantConnection.query.get(c1.id).percentual)), Decimal('0'))
        self.assertEqual(RateioHistorico.query.count(), 0)

    def test_sync_connections_rejects_new_link_above_100(self):
        from services.uc_service import sync_connections

        db.session.add(PlantConnection(empresa_id=1, plant_id=self.plant.id, consumer_unit_id=self.uc1.id, percentual=Decimal('80')))
        db.session.commit()

        with self.assertRaises(ValueError) as ctx:
            sync_connections(self.uc2, [{'plantId': self.plant.id, 'percentual': '25'}])
        self.assertIn('excede 100%', str(ctx.exception))
        self.assertEqual(PlantConnection.query.filter_by(consumer_unit_id=self.uc2.id).count(), 0)

        # dentro do limite (80 + 20 = 100) tem que ser aceito
        sync_connections(self.uc2, [{'plantId': self.plant.id, 'percentual': '20'}])
        self.assertEqual(PlantConnection.query.filter_by(consumer_unit_id=self.uc2.id).count(), 1)


if __name__ == '__main__':
    unittest.main()
