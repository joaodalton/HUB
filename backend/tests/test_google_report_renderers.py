import unittest
from unittest.mock import MagicMock, patch

from services.google_report_renderers import (
    MARCADOR_TABELA, ReportTable, render_as_doc, render_as_doc_from_template,
    render_as_sheet, render_as_sheet_from_template, render_as_slide, render_as_slide_from_template,
)
from services.report_templates import SYSTEM_TEMPLATES


def _table():
    return ReportTable(title='Cadastro', headers=['Nome', 'Codigo'], rows=[['Cliente A', 'UC-1'], ['Cliente B', 'UC-2']])


class GoogleReportRenderersTest(unittest.TestCase):
    @patch('services.google_report_renderers.build')
    def test_render_as_sheet_creates_file_and_writes_values(self, mock_build):
        drive_client = MagicMock()
        drive_client.files().create().execute.return_value = {'id': 'sheet-1', 'webViewLink': 'https://sheet-link'}
        sheets_client = MagicMock()
        mock_build.side_effect = lambda name, version, credentials: {'drive': drive_client, 'sheets': sheets_client}[name]

        result = render_as_sheet('fake-creds', _table(), parent_folder_id='folder-1')

        self.assertEqual(result, {'id': 'sheet-1', 'webViewLink': 'https://sheet-link'})
        sheets_client.spreadsheets().values().update.assert_called()

    @patch('services.google_report_renderers.build')
    def test_render_as_doc_creates_file_and_inserts_table(self, mock_build):
        drive_client = MagicMock()
        drive_client.files().create().execute.return_value = {'id': 'doc-1', 'webViewLink': 'https://doc-link'}
        docs_client = MagicMock()
        mock_build.side_effect = lambda name, version, credentials: {'drive': drive_client, 'docs': docs_client}[name]

        result = render_as_doc('fake-creds', _table(), parent_folder_id='folder-1')

        self.assertEqual(result, {'id': 'doc-1', 'webViewLink': 'https://doc-link'})
        docs_client.documents().batchUpdate.assert_called()

    @patch('services.google_report_renderers.build')
    def test_render_as_slide_creates_file_and_inserts_table(self, mock_build):
        drive_client = MagicMock()
        drive_client.files().create().execute.return_value = {'id': 'slide-1', 'webViewLink': 'https://slide-link'}
        slides_client = MagicMock()
        mock_build.side_effect = lambda name, version, credentials: {'drive': drive_client, 'slides': slides_client}[name]

        result = render_as_slide('fake-creds', _table(), parent_folder_id='folder-1')

        self.assertEqual(result, {'id': 'slide-1', 'webViewLink': 'https://slide-link'})
        slides_client.presentations().batchUpdate.assert_called()

    @patch('services.google_report_renderers.build')
    def test_render_as_slide_skips_insert_text_for_empty_cells(self, mock_build):
        drive_client = MagicMock()
        drive_client.files().create().execute.return_value = {'id': 'slide-2', 'webViewLink': 'https://slide-link-2'}
        slides_client = MagicMock()
        mock_build.side_effect = lambda name, version, credentials: {'drive': drive_client, 'slides': slides_client}[name]
        table = ReportTable(title='Cadastro', headers=['Nome', 'Codigo', 'UC'], rows=[['Cliente A', 'UC-1', '']])

        render_as_slide('fake-creds', table, parent_folder_id='folder-1')

        requests = slides_client.presentations().batchUpdate.call_args.kwargs['body']['requests']
        insert_text_requests = [r for r in requests if 'insertText' in r]
        self.assertTrue(all(r['insertText']['text'] != '' for r in insert_text_requests))
        self.assertLess(len(insert_text_requests), len(table.headers) * (len(table.rows) + 1))

    @patch('services.google_report_renderers.build')
    def test_render_as_sheet_com_template_padrao_nao_chama_batch_update(self, mock_build):
        drive_client = MagicMock()
        drive_client.files().create().execute.return_value = {'id': 'sheet-1', 'webViewLink': 'https://sheet-link'}
        sheets_client = MagicMock()
        mock_build.side_effect = lambda name, version, credentials: {'drive': drive_client, 'sheets': sheets_client}[name]

        render_as_sheet('fake-creds', _table(), parent_folder_id='folder-1', template=SYSTEM_TEMPLATES['padrao'])

        sheets_client.spreadsheets().batchUpdate.assert_not_called()

    @patch('services.google_report_renderers.build')
    def test_render_as_sheet_com_template_azul_formata_cabecalho(self, mock_build):
        drive_client = MagicMock()
        drive_client.files().create().execute.return_value = {'id': 'sheet-1', 'webViewLink': 'https://sheet-link'}
        sheets_client = MagicMock()
        mock_build.side_effect = lambda name, version, credentials: {'drive': drive_client, 'sheets': sheets_client}[name]

        render_as_sheet('fake-creds', _table(), parent_folder_id='folder-1', template=SYSTEM_TEMPLATES['azul'])

        sheets_client.spreadsheets().batchUpdate.assert_called_once()
        requests = sheets_client.spreadsheets().batchUpdate.call_args.kwargs['body']['requests']
        self.assertIn('repeatCell', requests[0])

    @patch('services.google_report_renderers.build')
    def test_render_as_doc_com_template_azul_estiliza_titulo_e_cabecalho(self, mock_build):
        drive_client = MagicMock()
        drive_client.files().create().execute.return_value = {'id': 'doc-1', 'webViewLink': 'https://doc-link'}
        docs_client = MagicMock()
        mock_build.side_effect = lambda name, version, credentials: {'drive': drive_client, 'docs': docs_client}[name]

        render_as_doc('fake-creds', _table(), parent_folder_id='folder-1', template=SYSTEM_TEMPLATES['azul'])

        requests = docs_client.documents().batchUpdate.call_args.kwargs['body']['requests']
        style_requests = [r for r in requests if 'updateTextStyle' in r]
        self.assertEqual(len(style_requests), 2)  # titulo + linha de cabecalho

    @patch('services.google_report_renderers.build')
    def test_render_as_slide_com_template_azul_formata_cabecalho(self, mock_build):
        drive_client = MagicMock()
        drive_client.files().create().execute.return_value = {'id': 'slide-1', 'webViewLink': 'https://slide-link'}
        slides_client = MagicMock()
        mock_build.side_effect = lambda name, version, credentials: {'drive': drive_client, 'slides': slides_client}[name]

        render_as_slide('fake-creds', _table(), parent_folder_id='folder-1', template=SYSTEM_TEMPLATES['azul'])

        requests = slides_client.presentations().batchUpdate.call_args.kwargs['body']['requests']
        cell_props_requests = [r for r in requests if 'updateTableCellProperties' in r]
        self.assertEqual(len(cell_props_requests), 2)  # 1 por coluna do cabecalho
        self.assertIn('tableRange', cell_props_requests[0]['updateTableCellProperties'])

    def test_empty_rows_do_not_raise(self):
        table = ReportTable(title='Vazio', headers=['Nome'], rows=[])
        with patch('services.google_report_renderers.build') as mock_build:
            drive_client = MagicMock()
            drive_client.files().create().execute.return_value = {'id': 'x', 'webViewLink': 'https://x'}
            sheets_client = MagicMock()
            mock_build.side_effect = lambda name, version, credentials: {'drive': drive_client, 'sheets': sheets_client}[name]
            result = render_as_sheet('fake-creds', table, parent_folder_id='folder-1')
            self.assertEqual(result['id'], 'x')

    @patch('services.google_report_renderers.build')
    def test_render_as_doc_from_template_copia_substitui_marcador_e_preenche_tabela(self, mock_build):
        drive_client = MagicMock()
        drive_client.files().copy().execute.return_value = {'id': 'copia-1', 'webViewLink': 'https://doc-copia'}
        docs_client = MagicMock()

        # 1a leitura: marcador "{{TABELA}}" dentro de "Antes {{TABELA}}\n", a partir do index 1
        doc_com_marcador = {'body': {'content': [{'paragraph': {'elements': [
            {'startIndex': 1, 'textRun': {'content': 'Antes '}},
            {'startIndex': 7, 'textRun': {'content': MARCADOR_TABELA}},
            {'startIndex': 17, 'textRun': {'content': '\n'}},
        ]}}]}}

        # 2a leitura (depois do delete+insertTable): tabela 3 linhas x 2 colunas
        doc_com_tabela = {'body': {'content': [{'table': {'tableRows': [
            {'tableCells': [
                {'content': [{'paragraph': {'elements': [{'startIndex': 100}]}}]},
                {'content': [{'paragraph': {'elements': [{'startIndex': 110}]}}]},
            ]},
            {'tableCells': [
                {'content': [{'paragraph': {'elements': [{'startIndex': 200}]}}]},
                {'content': [{'paragraph': {'elements': [{'startIndex': 210}]}}]},
            ]},
            {'tableCells': [
                {'content': [{'paragraph': {'elements': [{'startIndex': 300}]}}]},
                {'content': [{'paragraph': {'elements': [{'startIndex': 310}]}}]},
            ]},
        ]}}]}}

        docs_client.documents().get().execute.side_effect = [doc_com_marcador, doc_com_tabela]
        mock_build.side_effect = lambda name, version, credentials: {'drive': drive_client, 'docs': docs_client}[name]

        resultado = render_as_doc_from_template('fake-creds', 'drive-file-1', _table(), parent_folder_id='folder-1')

        self.assertEqual(resultado, {'id': 'copia-1', 'webViewLink': 'https://doc-copia'})
        drive_client.files().copy.assert_any_call(fileId='drive-file-1', body={'name': 'Cadastro', 'parents': ['folder-1']}, fields='id,webViewLink')

        primeira_chamada = docs_client.documents().batchUpdate.call_args_list[0]
        primeiros_requests = primeira_chamada.kwargs['body']['requests']
        self.assertEqual(primeiros_requests[0]['deleteContentRange']['range'], {'startIndex': 7, 'endIndex': 17})
        self.assertEqual(primeiros_requests[1]['insertTable'], {'rows': 3, 'columns': 2, 'location': {'index': 7}})

        segunda_chamada = docs_client.documents().batchUpdate.call_args_list[1]
        segundos_requests = segunda_chamada.kwargs['body']['requests']
        textos_por_indice = {r['insertText']['location']['index']: r['insertText']['text'] for r in segundos_requests}
        self.assertEqual(textos_por_indice, {
            100: 'Nome', 110: 'Codigo',
            200: 'Cliente A', 210: 'UC-1',
            300: 'Cliente B', 310: 'UC-2',
        })

    @patch('services.google_report_renderers.build')
    def test_render_as_doc_from_template_sem_marcador_levanta_erro(self, mock_build):
        drive_client = MagicMock()
        drive_client.files().copy().execute.return_value = {'id': 'copia-2', 'webViewLink': 'https://doc-copia-2'}
        docs_client = MagicMock()
        docs_client.documents().get().execute.return_value = {'body': {'content': [{'paragraph': {'elements': [
            {'startIndex': 1, 'textRun': {'content': 'Sem marcador aqui\n'}},
        ]}}]}}
        mock_build.side_effect = lambda name, version, credentials: {'drive': drive_client, 'docs': docs_client}[name]

        with self.assertRaises(ValueError):
            render_as_doc_from_template('fake-creds', 'drive-file-1', _table(), parent_folder_id='folder-1')
        docs_client.documents().batchUpdate.assert_not_called()

    @patch('services.google_report_renderers.build')
    def test_render_as_sheet_from_template_copia_e_escreve_a_partir_do_marcador(self, mock_build):
        drive_client = MagicMock()
        drive_client.files().copy().execute.return_value = {'id': 'copia-sheet', 'webViewLink': 'https://sheet-copia'}
        sheets_client = MagicMock()
        sheets_client.spreadsheets().get().execute.return_value = {'sheets': [{
            'properties': {'sheetId': 0, 'title': 'Página1'},
            'data': [{'rowData': [
                {},
                {'values': [{}, {'formattedValue': MARCADOR_TABELA}]},
            ]}],
        }]}
        mock_build.side_effect = lambda name, version, credentials: {'drive': drive_client, 'sheets': sheets_client}[name]

        resultado = render_as_sheet_from_template('fake-creds', 'drive-file-1', _table(), parent_folder_id='folder-1')

        self.assertEqual(resultado, {'id': 'copia-sheet', 'webViewLink': 'https://sheet-copia'})
        drive_client.files().copy.assert_any_call(fileId='drive-file-1', body={'name': 'Cadastro', 'parents': ['folder-1']}, fields='id,webViewLink')
        sheets_client.spreadsheets().values().update.assert_called_once_with(
            spreadsheetId='copia-sheet', range="'Página1'!B2", valueInputOption='RAW',
            body={'values': [['Nome', 'Codigo'], ['Cliente A', 'UC-1'], ['Cliente B', 'UC-2']]},
        )

    @patch('services.google_report_renderers.build')
    def test_render_as_sheet_from_template_sem_marcador_levanta_erro(self, mock_build):
        drive_client = MagicMock()
        drive_client.files().copy().execute.return_value = {'id': 'copia-sheet-2', 'webViewLink': 'https://sheet-copia-2'}
        sheets_client = MagicMock()
        sheets_client.spreadsheets().get().execute.return_value = {'sheets': [{
            'properties': {'sheetId': 0, 'title': 'Página1'},
            'data': [{'rowData': [{'values': [{'formattedValue': 'Sem marcador'}]}]}],
        }]}
        mock_build.side_effect = lambda name, version, credentials: {'drive': drive_client, 'sheets': sheets_client}[name]

        with self.assertRaises(ValueError):
            render_as_sheet_from_template('fake-creds', 'drive-file-1', _table(), parent_folder_id='folder-1')
        sheets_client.spreadsheets().values().update.assert_not_called()

    @patch('services.google_report_renderers.build')
    def test_render_as_slide_from_template_troca_shape_por_tabela_com_transform_normalizado(self, mock_build):
        drive_client = MagicMock()
        drive_client.files().copy().execute.return_value = {'id': 'copia-slide', 'webViewLink': 'https://slide-copia'}
        slides_client = MagicMock()
        slides_client.presentations().get().execute.return_value = {'slides': [{
            'objectId': 'page1',
            'pageElements': [{
                'objectId': 'markerShape',
                'transform': {'scaleX': 0.87, 'scaleY': 1.13, 'shearX': 0.02, 'translateX': 111, 'translateY': 222, 'unit': 'EMU'},
                'size': {'width': {'magnitude': 300, 'unit': 'EMU'}, 'height': {'magnitude': 400, 'unit': 'EMU'}},
                'shape': {'text': {'textElements': [{'textRun': {'content': MARCADOR_TABELA}}]}},
            }],
        }]}
        mock_build.side_effect = lambda name, version, credentials: {'drive': drive_client, 'slides': slides_client}[name]

        resultado = render_as_slide_from_template('fake-creds', 'drive-file-1', _table(), parent_folder_id='folder-1')

        self.assertEqual(resultado, {'id': 'copia-slide', 'webViewLink': 'https://slide-copia'})
        requests = slides_client.presentations().batchUpdate.call_args.kwargs['body']['requests']
        self.assertEqual(requests[0], {'deleteObject': {'objectId': 'markerShape'}})
        elemento_properties = requests[1]['createTable']['elementProperties']
        self.assertEqual(elemento_properties['transform'], {'scaleX': 1, 'scaleY': 1, 'translateX': 111, 'translateY': 222, 'unit': 'EMU'})
        self.assertEqual(elemento_properties['size'], {'width': {'magnitude': 300, 'unit': 'EMU'}, 'height': {'magnitude': 400, 'unit': 'EMU'}})
        self.assertEqual(requests[1]['createTable']['rows'], 3)
        self.assertEqual(requests[1]['createTable']['columns'], 2)

    @patch('services.google_report_renderers.build')
    def test_render_as_slide_from_template_sem_marcador_levanta_erro(self, mock_build):
        drive_client = MagicMock()
        drive_client.files().copy().execute.return_value = {'id': 'copia-slide-2', 'webViewLink': 'https://slide-copia-2'}
        slides_client = MagicMock()
        slides_client.presentations().get().execute.return_value = {'slides': [{'objectId': 'page1', 'pageElements': []}]}
        mock_build.side_effect = lambda name, version, credentials: {'drive': drive_client, 'slides': slides_client}[name]

        with self.assertRaises(ValueError):
            render_as_slide_from_template('fake-creds', 'drive-file-1', _table(), parent_folder_id='folder-1')
        slides_client.presentations().batchUpdate.assert_not_called()


if __name__ == '__main__':
    unittest.main()
