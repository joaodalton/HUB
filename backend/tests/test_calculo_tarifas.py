"""C5.2: tarifas manuais com energia sintética, sem comprovação de PDF GD."""
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal, localcontext, ROUND_DOWN
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.billing_calculation_contracts import (
    BillingCalculationContext, BillingModifiers, CalculationMemory, GracePeriod,
    ResolvedBillingRule, TariffConfiguration,
)
from services.billing_calculation_engine import (
    BillingCalculationEngine, BillingCalculationError, EstrategiaTarifaFixa,
    EstrategiaTarifaEspecifica,
)
from services.invoice_compensation import BillingEnergyInput
from services.invoice_normalization_service import InvoiceNormalizer, json_safe
from tests.test_invoice_compensation import parsed, found


class CalculoTarifasTest(unittest.TestCase):
    def setUp(self):
        self.contexto = BillingCalculationContext(1, 2, 4, 3, '2026-09')
        self.fatura = self.criar_fatura('1000')
        self.motor = BillingCalculationEngine()

    def criar_fatura(self, energia):
        fatura = InvoiceNormalizer().normalize(
            parsed((('sintetico', '2026-06', energia, energia),)), empresa_id=1,
            client_id=2, fatura_concessionaria_id=3)
        return replace(fatura, consumer_unit_id=4)

    def regra(self, metodo='tarifa_fixa', tarifa='0.70', desconto=None, **alteracoes):
        campos = dict(rule_id=1, rule_name='Tarifa manual', rule_version='8',
            source_scope='company', source_id=1, calculation_method=metodo,
            tariff_source='invoice', discount_type='none' if desconto is None else 'percentage',
            discount_value=None if desconto is None else Decimal(desconto),
            tariff_basis='compensated', billing_mode='auto', due_date_basis='invoice_due_date',
            due_date_offset_days=0, manual_tariff=None if tarifa is None else Decimal(tarifa))
        return ResolvedBillingRule(**{**campos, **alteracoes})

    def calcular(self, regra=None, fatura=None):
        return self.motor.calculate(invoice=self.fatura if fatura is None else fatura,
                                    rule=self.regra() if regra is None else regra, context=self.contexto)

    def verificar_bloqueio(self, codigo, regra, fatura=None):
        with self.assertRaises(BillingCalculationError) as erro:
            self.calcular(regra, fatura)
        self.assertEqual(erro.exception.code, codigo)

    def test_fixa_sem_desconto(self):
        for desconto in (None, '0'):
            resultado = self.calcular(self.regra(desconto=desconto))
            self.assertEqual((resultado.gross_base, resultado.discount_amount, resultado.hub_amount),
                             (Decimal('700'), Decimal('0'), Decimal('700.00')))

    def test_fixa_vinte_porcento(self):
        for tarifa, bruto, abatimento, liquido, efetiva in (
                ('0.70', '700', '140', '560.00', '0.56'), ('0.80', '800', '160', '640.00', '0.64')):
            resultado = self.calcular(self.regra(tarifa=tarifa, desconto='20'))
            self.assertEqual((resultado.gross_base, resultado.discount_amount, resultado.hub_amount),
                             tuple(map(Decimal, (bruto, abatimento, liquido))))
            self.assertEqual(resultado.calculation_memory.effective_company_tariff, Decimal(efetiva))
            self.assertTrue(resultado.calculation_memory.desconto_aplicado)

    def test_fixa_cem_porcento(self):
        self.assertEqual(self.calcular(self.regra(desconto='100')).hub_amount, Decimal('0.00'))

    def test_fixa_desconto_invalido(self):
        for desconto in ('-1', '100.01'):
            self.verificar_bloqueio('invalid_discount', self.regra(desconto=desconto))
        self.verificar_bloqueio('unsupported_discount_type',
                               self.regra(discount_type='fixed', discount_value=Decimal('20')))

    def test_fixa_tarifa_ausente(self):
        self.verificar_bloqueio('invalid_company_tariff', self.regra(tarifa=None))

    def test_tarifas_negativas(self):
        for metodo in ('tarifa_fixa', 'tarifa_especifica'):
            self.verificar_bloqueio('invalid_company_tariff', self.regra(metodo, tarifa='-0.7'))

    def test_especifica_basica(self):
        resultado = self.calcular(self.regra('tarifa_especifica', tarifa='0.56'))
        self.assertEqual((resultado.gross_base, resultado.discount_amount, resultado.hub_amount),
                         (Decimal('560'), Decimal('0'), Decimal('560.00')))

    def test_especifica_nao_aplica_desconto_compartilhado(self):
        for tipo, valor in (('percentage', '20'), ('fixed', '12'), ('percentage', '150')):
            regra = self.regra('tarifa_especifica', discount_type=tipo, discount_value=Decimal(valor))
            resultado = self.calcular(regra)
            self.assertEqual(resultado.hub_amount, Decimal('700.00'))
            self.assertEqual(resultado.discount_amount, Decimal('0'))
            memoria = resultado.calculation_memory
            self.assertFalse(memoria.desconto_aplicado)
            self.assertIsNone(memoria.discount_percentage)
            self.assertEqual(memoria.effective_company_tariff, Decimal('0.70'))
            self.assertEqual(resultado.rule_snapshot.to_dict()['discount_value'], valor)

    def test_especifica_tarifa_ausente_bloqueada_no_contrato_e_motor(self):
        with self.assertRaisesRegex(ValueError, 'companyTariff'):
            self.regra('tarifa_especifica', tarifa=None)
        # Defesa do motor para DTO adulterado; construtor normal já impede ausência.
        regra = self.regra('tarifa_especifica')
        object.__setattr__(regra, 'tariff_configuration', TariffConfiguration())
        self.verificar_bloqueio('invalid_company_tariff', regra)

    def test_estados_energeticos_bloqueiam_ambos(self):
        for metodo in ('tarifa_fixa', 'tarifa_especifica'):
            for estado in ('AMBIGUOUS', 'MISSING', 'UNSUPPORTED'):
                energia = replace(self.fatura.billing_energy_input, status=estado,
                                  energia_compensada_cobravel_kwh=None)
                self.verificar_bloqueio('required_energy_data_missing', self.regra(metodo),
                                       replace(self.fatura, billing_energy_input=energia))
            self.verificar_bloqueio('required_energy_data_missing', self.regra(metodo),
                                   replace(self.fatura, billing_energy_input=None))

    def test_energia_negativa_ou_ausente_nunca_corrigida(self):
        for metodo in ('tarifa_fixa', 'tarifa_especifica'):
            for valor in (Decimal('-1000'), None):
                with patch.object(BillingEnergyInput, 'require_valid', return_value=valor) as validar:
                    self.verificar_bloqueio('invalid_energy_input', self.regra(metodo))
                    validar.assert_called_once()

    def test_precisao_fixa(self):
        resultado = self.calcular(self.regra(tarifa='0.654321', desconto='17.5'), self.criar_fatura('333.333'))
        self.assertEqual(resultado.gross_base, Decimal('218.106781893'))
        self.assertEqual(resultado.discount_amount, Decimal('38.168686831275'))
        self.assertEqual(resultado.calculation_memory.net_amount_before_rounding, Decimal('179.938095061725'))
        self.assertEqual(resultado.calculation_memory.effective_company_tariff, Decimal('0.539814825'))
        self.assertEqual(resultado.hub_amount, Decimal('179.94'))

    def test_precisao_especifica_e_contexto_global(self):
        for metodo in ('tarifa_fixa', 'tarifa_especifica'):
            regra = self.regra(metodo, tarifa='0.654321', desconto='17.5')
            fatura = self.criar_fatura('333.333')
            esperado = self.calcular(regra, fatura)
            with localcontext() as contexto:
                contexto.prec = 3
                contexto.rounding = ROUND_DOWN
                self.assertEqual(self.calcular(regra, fatura), esperado)
            if metodo == 'tarifa_especifica':
                self.assertEqual(esperado.calculation_memory.net_amount_before_rounding, Decimal('218.106781893'))
                self.assertEqual(esperado.hub_amount, Decimal('218.11'))

    def test_arredondamento_somente_final(self):
        fatura = self.criar_fatura('1')
        fixa = self.calcular(self.regra(tarifa='0.025', desconto='20'), fatura)
        self.assertEqual((fixa.gross_base, fixa.discount_amount, fixa.hub_amount),
                         (Decimal('0.025'), Decimal('0.005'), Decimal('0.02')))
        especifica = self.calcular(self.regra('tarifa_especifica', tarifa='0.005', desconto='20'), fatura)
        self.assertEqual(especifica.gross_base, Decimal('0.005'))
        self.assertEqual(especifica.hub_amount, Decimal('0.01'))

    def test_selecao_das_estrategias(self):
        for metodo, estrategia in (('tarifa_fixa', EstrategiaTarifaFixa),
                                   ('tarifa_especifica', EstrategiaTarifaEspecifica)):
            regra = self.regra(metodo)
            with patch.object(estrategia, 'calculate', return_value='resultado') as calcular:
                self.assertEqual(self.calcular(regra), 'resultado')
                calcular.assert_called_once_with(invoice=self.fatura, rule=regra, context=self.contexto)

    def test_metodos_ainda_nao_suportados(self):
        for metodo in ('valor_total_fatura', 'economia_gerada', 'tarifa_fixa_com_desconto', 'energia_recebida'):
            self.verificar_bloqueio('unsupported_calculation_method', self.regra(metodo, desconto='20'))

    def test_diferenca_semantica_e_regressao_compensada(self):
        resultados = {metodo: self.calcular(self.regra(metodo, desconto='20')).hub_amount
                      for metodo in ('energia_compensada', 'tarifa_fixa', 'tarifa_especifica')}
        self.assertEqual(resultados, {'energia_compensada': Decimal('560.00'),
                                     'tarifa_fixa': Decimal('560.00'), 'tarifa_especifica': Decimal('700.00')})

    def test_valores_documentais_nao_sao_fallback(self):
        fatura = replace(self.fatura, campos={chave: found(Decimal(valor)) for chave, valor in (
            ('tarifa_concessionaria', '0.90'), ('saldo_credito_kwh', '10000'),
            ('energia_injetada_kwh', '5000'), ('valor_total_concessionaria', '850'))})
        for metodo in ('tarifa_fixa', 'tarifa_especifica'):
            self.assertEqual(self.calcular(self.regra(metodo), fatura).hub_amount, Decimal('700.00'))
        self.verificar_bloqueio('invalid_company_tariff', self.regra(tarifa=None), fatura)

    def test_zero_explicito_valido(self):
        for metodo in ('tarifa_fixa', 'tarifa_especifica'):
            self.assertEqual(self.calcular(self.regra(metodo, tarifa='0')).hub_amount, Decimal('0.00'))

    def test_memoria_snapshot_determinismo_sem_mutacao(self):
        for metodo in ('tarifa_fixa', 'tarifa_especifica'):
            regra = self.regra(metodo, desconto='20', metadata={'origem': 'original'})
            antes = deepcopy(json_safe((regra, self.fatura)))
            resultado = self.calcular(regra)
            self.assertEqual(resultado.to_dict(), self.calcular(regra).to_dict())
            self.assertEqual(antes, json_safe((regra, self.fatura)))
            regra.metadata['origem'] = 'alterada'
            self.assertEqual(resultado.rule_snapshot.to_dict()['metadata']['origem'], 'original')
            self.assertEqual(resultado.rule_snapshot.to_dict()['calculation_method'], metodo)
            self.assertEqual(resultado.rule_snapshot.to_dict()['rule_version'], '8')
            self.assertIsInstance(resultado.calculation_memory.company_tariff_used, Decimal)
        with self.assertRaises(ValueError):
            CalculationMemory(desconto_aplicado=0)

    def test_modificadores_continuam_bloqueados(self):
        for metodo in ('tarifa_fixa', 'tarifa_especifica'):
            for modificadores in (BillingModifiers(exclude_pis_cofins=True), BillingModifiers(icms_policy='exclude'),
                    BillingModifiers(exclude_tariff_flag=True), BillingModifiers(grace_period=GracePeriod(True)),
                    BillingModifiers(recurring_additional_cost=Decimal('1'))):
                self.verificar_bloqueio('unsupported_billing_configuration',
                                       self.regra(metodo, billing_modifiers=modificadores))


if __name__ == '__main__':
    unittest.main()
