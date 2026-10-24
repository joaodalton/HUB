import unittest
from unittest.mock import Mock, patch

from services.drive_service import GoogleDriveService


class DriveFolderTest(unittest.TestCase):
    def setUp(self):
        self.client = Mock()
        with patch('services.drive_service.build', return_value=self.client):
            self.service = GoogleDriveService(object(), 'root')

    def test_lists_files_in_a_nested_tenant_folder(self):
        self.client.files().get.return_value.execute.side_effect = [
            {'id': 'folder', 'mimeType': 'application/vnd.google-apps.folder', 'parents': ['nested']},
            {'id': 'nested', 'parents': ['root']},
        ]
        self.client.files().list.return_value.execute.return_value = {'files': [{'id': 'file', 'name': 'Conta.pdf'}]}

        self.assertEqual(self.service.list_folder('folder'), [{'id': 'file', 'name': 'Conta.pdf'}])
        self.assertIn("'folder' in parents", self.client.files().list.call_args.kwargs['q'])

    def test_rejects_folder_outside_tenant_root(self):
        self.client.files().get.return_value.execute.side_effect = [
            {'id': 'foreign', 'mimeType': 'application/vnd.google-apps.folder', 'parents': ['other-root']},
            {'id': 'other-root', 'parents': []},
        ]

        with self.assertRaisesRegex(ValueError, 'Pasta nao encontrada'):
            self.service.list_folder('foreign')
        self.client.files().list.assert_not_called()

    def test_rejects_file_outside_tenant_root(self):
        self.client.files().get.return_value.execute.side_effect = [
            {'id': 'foreign-file', 'name': 'Conta.pdf', 'parents': ['other-root']},
            {'id': 'other-root', 'parents': []},
        ]

        with self.assertRaisesRegex(ValueError, 'Arquivo do Google Drive nao encontrado'):
            self.service.get_authorized_item('foreign-file')


if __name__ == '__main__':
    unittest.main()
