import unittest
from unittest.mock import MagicMock, patch

from services.reports_service import gerar_relatorio
from services.google_reports_auth import ReportScopeError, ReportAccountMissingError


class ReportsServiceTest(unittest.TestCase):
    def test_tipo_invalido_levanta_value_error(self):
        with self.assertRaises(ValueError):
            gerar_relatorio(empresa_id=1, tipo='inexistente', formato='sheet')

    def test_formato_invalido_levanta_value_error(self):
        with self.assertRaises(ValueError):
            gerar_relatorio(empresa_id=1, tipo='cadastro', formato='inexistente')

    @patch('services.reports_service.get_report_credentials')
    def test_scope_error_propaga(self, mock_creds):
        mock_creds.side_effect = ReportScopeError(['x'])
        with self.assertRaises(ReportScopeError):
            gerar_relatorio(empresa_id=1, tipo='cadastro', formato='sheet')

    @patch('services.reports_service.get_report_credentials')
    def test_account_missing_propaga(self, mock_creds):
        mock_creds.side_effect = ReportAccountMissingError('sem conta')
        with self.assertRaises(ReportAccountMissingError):
            gerar_relatorio(empresa_id=1, tipo='cadastro', formato='sheet')

    @patch('services.reports_service._coletar_cadastro')
    @patch('services.reports_service._pasta_relatorios')
    @patch('services.reports_service.get_report_credentials')
    @patch('services.reports_service.render_as_sheet')
    def test_gerar_relatorio_cadastro_sheet_chama_renderer_certo(self, mock_render, mock_creds, mock_pasta, mock_coletar):
        mock_creds.return_value = 'creds'
        mock_pasta.return_value = 'folder-1'
        mock_coletar.return_value = MagicMock(title='Cadastro', headers=['Nome'], rows=[])
        mock_render.return_value = {'id': 'abc', 'webViewLink': 'https://x'}

        result = gerar_relatorio(empresa_id=1, tipo='cadastro', formato='sheet')

        self.assertEqual(result, {'driveFileId': 'abc', 'webViewLink': 'https://x'})
        mock_render.assert_called_once_with('creds', mock_coletar.return_value, parent_folder_id='folder-1')

    @patch('services.reports_service.list_plants')
    @patch('services.reports_service.list_ucs')
    @patch('services.reports_service.list_clients')
    def test_coletar_cadastro_mascara_documento_e_monta_linhas(self, mock_clients, mock_ucs, mock_plants):
        from services.reports_service import _coletar_cadastro
        mock_clients.return_value = [{'id': 1, 'nome': 'Cliente A', 'documento': '123.456.789-00'}]
        mock_ucs.return_value = [{'id': 10, 'codigo': 'UC-1', 'clientId': 1}]
        mock_plants.return_value = [{'id': 100, 'nome': 'Usina X'}]

        tabela = _coletar_cadastro(empresa_id=1, competencia=None)

        self.assertIn('Nome', tabela.headers)
        self.assertNotIn('123.456.789-00', str(tabela.rows))
        self.assertTrue(any('Cliente A' in row for row in tabela.rows))


if __name__ == '__main__':
    unittest.main()
