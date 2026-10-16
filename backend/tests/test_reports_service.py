import unittest
from unittest.mock import MagicMock, patch

from services import reports_service
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

    @patch('services.reports_service._pasta_relatorios')
    @patch('services.reports_service.get_report_credentials')
    def test_gerar_relatorio_cadastro_sheet_chama_renderer_certo(self, mock_creds, mock_pasta):
        mock_creds.return_value = 'creds'
        mock_pasta.return_value = 'folder-1'
        mock_coletor = MagicMock(return_value=MagicMock(title='Cadastro', headers=['Nome'], rows=[]))
        mock_render = MagicMock(return_value={'id': 'abc', 'webViewLink': 'https://x'})

        with patch.object(reports_service, '_COLETORES', {**reports_service._COLETORES, 'cadastro': mock_coletor}), \
                patch.object(reports_service, '_RENDERERS', {**reports_service._RENDERERS, 'sheet': mock_render}):
            result = gerar_relatorio(empresa_id=1, tipo='cadastro', formato='sheet')

        self.assertEqual(result, {'driveFileId': 'abc', 'webViewLink': 'https://x'})
        mock_render.assert_called_once_with('creds', mock_coletor.return_value, parent_folder_id='folder-1')

    @patch('services.reports_service.listar_faturas')
    def test_coletar_financeiro_agrupa_por_competencia(self, mock_listar):
        from services.reports_service import _coletar_financeiro
        mock_listar.return_value = [
            {'competencia': '2026-09', 'clienteNome': 'Cliente A', 'ucCodigo': 'UC-1', 'valor': 560.0, 'mesVencimento': '2026-09-10', 'statusInterno': 'emitida', 'asaasStatus': 'received'},
            {'competencia': '2026-09', 'clienteNome': 'Cliente B', 'ucCodigo': 'UC-2', 'valor': 0.0, 'mesVencimento': '2026-09-15', 'statusInterno': 'aguardando_emissao', 'asaasStatus': 'pending'},
        ]

        tabela = _coletar_financeiro(empresa_id=1, competencia='2026-09')

        mock_listar.assert_called_once_with(1, {'competencia': '2026-09'})
        self.assertEqual(len(tabela.rows), 2)
        self.assertIn('Cliente', tabela.headers)
        self.assertIn('UC', tabela.headers)
        self.assertEqual(tabela.rows[0][1], 'Cliente A')
        self.assertEqual(tabela.rows[0][2], 'UC-1')
        self.assertEqual(tabela.rows[0][3], '560.00')
        self.assertEqual(tabela.rows[1][3], '0.00')

    @patch('services.reports_service.list_plants')
    @patch('services.reports_service.list_ucs')
    @patch('services.reports_service.list_clients')
    def test_coletar_cadastro_mascara_documento_e_monta_linhas(self, mock_clients, mock_ucs, mock_plants):
        from services.reports_service import _coletar_cadastro
        mock_clients.return_value = [{'id': 1, 'nome': 'Cliente A', 'cpf': '123.456.789-00'}]
        mock_ucs.return_value = [{'id': 10, 'codigo': 'UC-1', 'clientId': 1}]
        mock_plants.return_value = [{'id': 100, 'nome': 'Usina X'}]

        tabela = _coletar_cadastro(empresa_id=1, competencia=None)

        self.assertIn('Nome', tabela.headers)
        self.assertNotIn('123.456.789-00', str(tabela.rows))
        self.assertTrue(any('Cliente A' in row for row in tabela.rows))

    @patch('services.reports_service.list_historico_rateio')
    def test_coletar_rateio_monta_linhas_usina_uc(self, mock_historico):
        from services.reports_service import _coletar_rateio
        mock_historico.return_value = [
            {'competencia': '2026-09', 'usinaNome': 'Usina X', 'ucCodigo': 'UC-1', 'percentual': 50.0},
        ]

        tabela = _coletar_rateio(empresa_id=1, competencia='2026-09')

        mock_historico.assert_called_once_with(competencia='2026-09')
        self.assertEqual(tabela.rows[0][1], 'Usina X')


if __name__ == '__main__':
    unittest.main()
