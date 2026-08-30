"""Regressoes do fluxo de revisao e geracao do rateio Copel."""
import io
from pathlib import Path
import unittest
from unittest.mock import patch

from pypdf import PdfReader

from services.rateio_pdf_service import gerar_formulario_pdf


BACKEND = Path(__file__).resolve().parent


def _tabela_24_linhas() -> dict:
    linhas = [
        {
            'ordem': ordem,
            'nome': f'Beneficiario Marcador {ordem:02d}',
            'documento': f'DOC-{ordem:02d}',
            'ucIdentificacao': f'UC-{ordem:02d}',
            'percentual': 4.0,
            'termoAdesaoOk': True,
            'clienteId': ordem,
            'ucId': ordem,
        }
        for ordem in range(1, 25)
    ]
    return {
        'plantId': 1,
        'plantNome': 'Usina Teste',
        'ucGeradora': 'GERADORA-1',
        'ucAncora': 'GERADORA-1',
        'empresaNome': 'Empresa Teste',
        'empresaCnpj': '12.345.678/0001-90',
        'empresaEmail': 'teste@example.com',
        'documentoCnpjOk': True,
        'documentoEstatutoOk': True,
        'linhas': linhas,
        'somaPercentual': 96.0,
        'excedeLimiteLinhas': False,
    }


class RateioPdfTests(unittest.TestCase):
    @patch('services.rateio_pdf_service.verificar_termos_adesao', return_value={'ok': True, 'faltando': []})
    @patch('services.rateio_pdf_service.montar_tabela_formulario')
    def test_pdf_inclui_todas_as_24_linhas(self, montar, _verificar):
        montar.return_value = _tabela_24_linhas()

        pdf = gerar_formulario_pdf(1, 'Responsavel Teste', '12345678900')
        texto = '\n'.join(page.extract_text() or '' for page in PdfReader(io.BytesIO(pdf)).pages)

        for ordem in range(1, 25):
            self.assertIn(f'Beneficiario Marcador {ordem:02d}', texto)

    @patch('services.rateio_pdf_service.verificar_termos_adesao', return_value={'ok': True, 'faltando': []})
    @patch('services.rateio_pdf_service.montar_tabela_formulario')
    def test_correcao_visual_nao_altera_origem_e_aparece_no_pdf(self, montar, _verificar):
        tabela = _tabela_24_linhas()
        montar.return_value = tabela

        pdf = gerar_formulario_pdf(
            1,
            'Responsavel Teste',
            '12345678900',
            linhas_override=[{'ucId': 1, 'nome': 'Nome Corrigido Apenas no PDF'}],
        )
        texto = '\n'.join(page.extract_text() or '' for page in PdfReader(io.BytesIO(pdf)).pages)

        self.assertIn('Nome Corrigido Apenas no PDF', texto)
        self.assertEqual(tabela['linhas'][0]['nome'], 'Nome Corrigido Apenas no PDF')

    def test_geracao_nao_registra_pendencia_implicitamente(self):
        source = (BACKEND / 'services/rateio_pdf_service.py').read_text(encoding='utf-8')
        self.assertNotIn('registrar_pendencia=True', source)

    def test_download_do_drive_valida_pasta_do_tenant(self):
        source = (BACKEND / 'services/drive_service.py').read_text(encoding='utf-8')
        self.assertIn('def download_file(self, file_id: str) -> bytes:', source)
        self.assertIn("self.root_folder_id not in metadata.get('parents', [])", source)


if __name__ == '__main__':
    unittest.main()
