import io
import unittest
from copy import deepcopy
from unittest.mock import patch

from openpyxl import load_workbook

from services.rateio_excel_service import _carregar_modelo, gerar_formulario_excel


def _tabela(percentual=50.0):
    return {
        'plantId': 1, 'plantNome': 'Usina A', 'ucGeradora': 'GER-1', 'ucAncora': 'GER-1',
        'empresaNome': 'Associacao A', 'empresaCnpj': '12345678000199', 'empresaEmail': 'a@test.local',
        'documentoCnpjOk': True, 'documentoEstatutoOk': True,
        'regrasDocumentos': {'documentoCnpjObrigatorio': True, 'documentoEstatutoObrigatorio': True, 'termosAdesaoObrigatorios': True},
        'linhas': [{'ordem': 1, 'nome': 'Ana', 'documento': '12345678901', 'ucIdentificacao': 'UC-1',
                    'percentual': percentual, 'termoAdesaoOk': True, 'clienteId': 1, 'ucId': 1}],
        'somaPercentual': percentual,
    }


class RateioExcelTest(unittest.TestCase):
    def gerar(self, tabela, **kwargs):
        with patch('services.rateio_excel_service.montar_tabela_formulario', return_value=tabela), \
             patch('services.rateio_excel_service.get_regras_documentos_rateio', return_value=tabela['regrasDocumentos']), \
             patch('services.rateio_excel_service.verificar_termos_adesao', return_value={'ok': True, 'faltando': []}):
            return gerar_formulario_excel(1, 'Responsavel', '12345678901', **kwargs)

    def test_fills_association_and_static_total(self):
        sheet = load_workbook(io.BytesIO(self.gerar(_tabela(), linhas_override=[{'ucId': 1, 'nome': 'Ana Revisada', 'percentual': 55}], excedente_energia=True))).active
        self.assertIn('GER-1', sheet['A4'].value)
        self.assertIn('GER-1', sheet['A8'].value)
        self.assertEqual(sheet['A11'].value, 'SIM')
        self.assertEqual(sheet['B17'].value, 'Associacao A')
        self.assertEqual(sheet['B18'].value, 'Ana Revisada')
        self.assertEqual(sheet['E41'].value, .55)
        self.assertEqual(sheet['C72'].value, 'a@test.local')

    def test_expands_and_rebuilds_lower_merges(self):
        tabela = _tabela(4)
        tabela['linhas'] = [dict(deepcopy(tabela['linhas'][0]), ordem=i, ucId=i) for i in range(1, 26)]
        sheet = load_workbook(io.BytesIO(self.gerar(tabela))).active
        self.assertEqual(sheet['A42'].value, 26)
        self.assertEqual(sheet['E43'].value, 1)
        self.assertIn('A43:D43', {str(merge) for merge in sheet.merged_cells.ranges})
        self.assertEqual(sheet['C73'].value, 'Associacao A')

    def test_template_placeholder_must_exist(self):
        workbook = _carregar_modelo()
        workbook.active['A4'] = 'Texto sem placeholder'
        with patch('services.rateio_excel_service._carregar_modelo', return_value=workbook), \
             patch('services.rateio_excel_service.montar_tabela_formulario', return_value=_tabela()), \
             patch('services.rateio_excel_service.get_regras_documentos_rateio', return_value=_tabela()['regrasDocumentos']), \
             patch('services.rateio_excel_service.verificar_termos_adesao', return_value={'ok': True, 'faltando': []}):
            with self.assertRaisesRegex(ValueError, 'Placeholder de UC geradora'):
                gerar_formulario_excel(1, 'Responsavel', '12345678901')

    def test_rejects_total_over_100(self):
        with self.assertRaisesRegex(ValueError, 'excede 100'):
            self.gerar(_tabela(100.01))


if __name__ == '__main__':
    unittest.main()
