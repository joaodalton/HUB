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


if __name__ == '__main__':
    unittest.main()
