import unittest
from unittest.mock import MagicMock, patch

from services.google_report_renderers import ReportTable, render_as_sheet, render_as_doc, render_as_slide


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

    def test_empty_rows_do_not_raise(self):
        table = ReportTable(title='Vazio', headers=['Nome'], rows=[])
        with patch('services.google_report_renderers.build') as mock_build:
            drive_client = MagicMock()
            drive_client.files().create().execute.return_value = {'id': 'x', 'webViewLink': 'https://x'}
            sheets_client = MagicMock()
            mock_build.side_effect = lambda name, version, credentials: {'drive': drive_client, 'sheets': sheets_client}[name]
            result = render_as_sheet('fake-creds', table, parent_folder_id='folder-1')
            self.assertEqual(result['id'], 'x')


if __name__ == '__main__':
    unittest.main()
