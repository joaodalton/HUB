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

    def test_authorizes_legitimate_child_when_google_omits_parents_field(self):
        # Reproduz o bug real: files().get() devolve o item SEM 'parents' (compartilhamento
        # direto, nao posse), mesmo sendo filho legitimo da raiz. Fallback descendente
        # (mesma query de list_folder) deve confirmar e autorizar -- sem fail-open.
        self.client.files().get.return_value.execute.return_value = {
            'id': 'shared-folder', 'name': 'Pasta Compartilhada',
            'mimeType': 'application/vnd.google-apps.folder'
        }
        self.client.files().list.return_value.execute.return_value = {
            'files': [{'id': 'shared-folder', 'mimeType': 'application/vnd.google-apps.folder'}]
        }

        metadata = self.service.get_authorized_item('shared-folder')
        self.assertEqual(metadata['id'], 'shared-folder')

    def test_rejects_unknown_id_even_when_google_omits_parents_field(self):
        # Mesma ausencia de 'parents', mas o ID nunca foi listado como filho da raiz --
        # fail-closed precisa se manter (nao pode confiar so na ausencia do campo).
        self.client.files().get.return_value.execute.return_value = {
            'id': 'random-id', 'name': 'Alguma coisa',
            'mimeType': 'application/vnd.google-apps.document'
        }
        self.client.files().list.return_value.execute.return_value = {'files': []}

        with self.assertRaisesRegex(ValueError, 'Arquivo do Google Drive nao encontrado'):
            self.service.get_authorized_item('random-id')

    def test_list_root_delegates_to_list_folder_when_root_configured(self):
        self.client.files().get.return_value.execute.side_effect = [
            {'id': 'root', 'mimeType': 'application/vnd.google-apps.folder', 'parents': []},
        ]
        self.client.files().list.return_value.execute.return_value = {'files': [{'id': 'file', 'name': 'Conta.pdf'}]}

        self.assertEqual(self.service.list_root(), [{'id': 'file', 'name': 'Conta.pdf'}])
        self.assertIn("'root' in parents", self.client.files().list.call_args.kwargs['q'])


    def test_caches_confirmed_descendant_to_avoid_repeated_list_calls(self):
        self.client.files().list.return_value.execute.return_value = {
            'files': [{'id': 'shared-folder', 'mimeType': 'application/vnd.google-apps.folder'}]
        }

        self.assertTrue(self.service._is_within_root('shared-folder', []))
        self.assertTrue(self.service._is_within_root('shared-folder', []))
        self.assertEqual(self.client.files().list.return_value.execute.call_count, 1)

    def test_descends_from_root_through_intermediate_folder_to_find_grandchild(self):
        self.client.files().list.return_value.execute.side_effect = [
            {'files': [{'id': 'intermediate', 'mimeType': 'application/vnd.google-apps.folder'}]},
            {'files': [{'id': 'target', 'mimeType': 'application/vnd.google-apps.document'}]},
        ]

        self.assertTrue(self.service._descends_from_root('target'))
        self.assertEqual(self.client.files().list.return_value.execute.call_count, 2)

    def test_descends_from_root_paginates_until_item_found(self):
        self.client.files().list.return_value.execute.side_effect = [
            {'files': [], 'nextPageToken': 'page-2'},
            {'files': [{'id': 'target', 'mimeType': 'application/vnd.google-apps.document'}]},
        ]

        self.assertTrue(self.service._descends_from_root('target'))
        second_call_kwargs = self.client.files().list.call_args_list[1].kwargs
        self.assertEqual(second_call_kwargs['pageToken'], 'page-2')


class DriveRootAliasTest(unittest.TestCase):
    def setUp(self):
        self.client = Mock()
        with patch('services.drive_service.build', return_value=self.client):
            self.service = GoogleDriveService(object(), '')

    def test_list_root_uses_root_alias_when_no_tenant_root_configured(self):
        self.client.files().list.return_value.execute.return_value = {'files': [{'id': 'file', 'name': 'Conta.pdf'}]}

        self.assertEqual(self.service.list_root(), [{'id': 'file', 'name': 'Conta.pdf'}])
        self.client.files().get.assert_not_called()
        self.assertIn("'root' in parents", self.client.files().list.call_args.kwargs['q'])


if __name__ == '__main__':
    unittest.main()
