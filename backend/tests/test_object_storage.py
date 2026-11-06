"""STORAGE-1: domain-neutral local/S3 object operations and safe configuration."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flask import Flask
from services.object_storage import LegacyDriveObjectStorage, LocalObjectStorage, S3ObjectStorage, ObjectStorageError, get_object_storage


class ObjectStorageTest(unittest.TestCase):
    def test_provider_config_fails_closed_in_production(self):
        app = Flask(__name__)
        app.config.update(DEBUG=False, TESTING=False, STORAGE_PROVIDER='',
                          OBJECT_STORAGE_LOCAL_DIR='unused')
        with app.app_context():
            with self.assertRaises(ObjectStorageError):
                get_object_storage()
            app.config['STORAGE_PROVIDER'] = 'local'
            with self.assertRaises(ObjectStorageError):
                get_object_storage()

    def test_s3_factory_uses_server_credentials_and_https_endpoint(self):
        app = Flask(__name__)
        app.config.update(DEBUG=False, TESTING=False, STORAGE_PROVIDER='s3',
            OBJECT_STORAGE_ENDPOINT='https://account.r2.cloudflarestorage.com',
            OBJECT_STORAGE_BUCKET='private-bucket', OBJECT_STORAGE_ACCESS_KEY_ID='id',
            OBJECT_STORAGE_SECRET_ACCESS_KEY='secret', OBJECT_STORAGE_REGION='auto')
        with app.app_context(), patch('boto3.client', return_value=Mock()) as client:
            self.assertIsInstance(get_object_storage(), S3ObjectStorage)
            client.assert_called_once_with('s3',
                endpoint_url='https://account.r2.cloudflarestorage.com',
                aws_access_key_id='id', aws_secret_access_key='secret', region_name='auto')
            app.config['OBJECT_STORAGE_ENDPOINT'] = 'http://account.r2.cloudflarestorage.com'
            with self.assertRaises(ObjectStorageError):
                get_object_storage()
            app.config['OBJECT_STORAGE_ENDPOINT'] = 'https://other.example.com'
            with self.assertRaises(ObjectStorageError):
                get_object_storage()

    def test_local_roundtrip_and_rejects_path_escape(self):
        with tempfile.TemporaryDirectory() as folder:
            storage = LocalObjectStorage(Path(folder))
            storage.put('tenants/1/invoices/2026/09/id.pdf', b'%PDF-test', 'application/pdf')
            self.assertEqual(storage.read('tenants/1/invoices/2026/09/id.pdf', 10), b'%PDF-test')
            with self.assertRaises(ObjectStorageError):
                storage.read('../escape.pdf', 10)
            storage.delete('tenants/1/invoices/2026/09/id.pdf')
            with self.assertRaises(ObjectStorageError):
                storage.read('tenants/1/invoices/2026/09/id.pdf', 10)

    def test_s3_adapter_uses_bucket_key_and_bounds_read(self):
        body = Mock()
        body.read.return_value = b'%PDF-test'
        client = Mock()
        client.get_object.return_value = {'Body': body}
        storage = S3ObjectStorage(client, 'private-bucket')
        storage.put('opaque.pdf', b'%PDF-test', 'application/pdf')
        self.assertEqual(storage.read('opaque.pdf', 10), b'%PDF-test')
        storage.delete('opaque.pdf')
        client.put_object.assert_called_once_with(Bucket='private-bucket', Key='opaque.pdf', Body=b'%PDF-test', ContentType='application/pdf')
        client.get_object.assert_called_once_with(Bucket='private-bucket', Key='opaque.pdf')
        body.read.assert_called_once_with(11)
        body.close.assert_called_once()
        client.delete_object.assert_called_once_with(Bucket='private-bucket', Key='opaque.pdf')

    def test_legacy_drive_adapter_is_read_only_and_bounded(self):
        app = Flask(__name__)
        drive = Mock()
        drive.download_file.return_value = b'%PDF-legacy'
        with app.app_context(), patch('services.drive_service.get_drive_service', return_value=drive):
            storage = get_object_storage('google_drive')
            self.assertIsInstance(storage, LegacyDriveObjectStorage)
            self.assertEqual(storage.read('legacy-id', 20), b'%PDF-legacy')
            with self.assertRaises(ObjectStorageError):
                storage.read('legacy-id', 3)
            drive.download_file.assert_called_with('legacy-id')


if __name__ == '__main__':
    unittest.main()
