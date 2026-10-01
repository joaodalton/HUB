import hashlib
import io
import os
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from unittest.mock import patch

from pypdf import PdfWriter


_DB = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_DB.close()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from extensions import db
from models.client import Client
from models.consumer_unit import ConsumerUnit
from models.document import Document
from models.empresa import Empresa
from models.fatura_concessionaria import FaturaConcessionaria
from models.google_account import GoogleAccount
from models.user import User
from services import fatura_concessionaria_upload_service as upload_service
from services import drive_service
from services.object_storage import LegacyDriveObjectStorage, LocalObjectStorage
from services.uc_code import normalize_uc_code
try:
    from .fixtures.invoices.copel.build_fixture import make_pdf
except ImportError:
    from fixtures.invoices.copel.build_fixture import make_pdf
from utils.auth import generate_token
try:
    from .support import IsolatedTestRuntime
except ImportError:
    from support import IsolatedTestRuntime


class FakeDrive:
    root_folder_id = 'test-root'

    def __init__(self):
        self.files = {}
        self.deleted = []
        self._lock = threading.Lock()

    def find_duplicate(self, name, md5, _parent):
        with self._lock:
            return next((
                file_id for file_id, item in self.files.items()
                if item['name'] == name and item['md5'] == md5
            ), None)

    def upload_file(self, file_bytes, name, mime_type, _parent):
        with self._lock:
            file_id = f'file-{len(self.files) + 1}'
            self.files[file_id] = {
                'bytes': file_bytes,
                'name': name,
                'mime': mime_type,
                'md5': hashlib.md5(file_bytes).hexdigest(),
            }
            return file_id

    def delete_file(self, file_id):
        with self._lock:
            self.deleted.append(file_id)
            self.files.pop(file_id, None)

    def download_file(self, file_id):
        return self.files[file_id]['bytes']


class FakeObjectStore:
    provider = 's3'

    def __init__(self):
        self.files = {}
        self.deleted = []
        self._lock = threading.Lock()

    def put(self, key, data, content_type):
        with self._lock:
            self.files[key] = data

    def read(self, key, max_bytes):
        with self._lock:
            return self.files[key][:max_bytes + 1]

    def delete(self, key):
        with self._lock:
            self.deleted.append(key)
            self.files.pop(key, None)


class FaturaConcessionariaUploadTest(IsolatedTestRuntime, unittest.TestCase):
    def test_copel_code_normalization_preserves_leading_zeros_and_other_distributors(self):
        self.assertEqual(normalize_uc_code('000000000001', 'Copel'), '000000000000001')
        self.assertEqual(normalize_uc_code('000000000000001', 'Copel'), '000000000000001')
        self.assertEqual(normalize_uc_code('570778003105', 'Outra'), '570778003105')
        self.assertEqual(normalize_uc_code(' UC-01 ', 'Outra'), ' UC-01 ')
        with self.assertRaises(ValueError):
            normalize_uc_code('   ', 'Outra')
        for invalid in ('123', '1234567890123', '1234567890123456', 'ABCDEFGHIJKL'):
            with self.assertRaises(ValueError):
                normalize_uc_code(invalid, 'Copel')

    def test_copel_uc_create_and_edit_normalize_code(self):
        client = self.app.test_client()
        headers = {'Authorization': f'Bearer {self._token("owner@a.test")}' }
        created = client.post('/api/v1/ucs', headers=headers, json={
            'clienteId': 1, 'codigo': '000000000001', 'concessionaria': 'Copel',
        })
        self.assertEqual(created.status_code, 201, created.json)
        uc_id = created.json['data']['id']
        self.assertEqual(created.json['data']['codigo'], '000000000000001')
        edited = client.put(f'/api/v1/ucs/{uc_id}', headers=headers, json={'codigo': '570778003105'})
        self.assertEqual(edited.status_code, 200, edited.json)
        self.assertEqual(edited.json['data']['codigo'], '000570778003105')
        invalid = client.put(f'/api/v1/ucs/{uc_id}', headers=headers, json={'codigo': '123'})
        self.assertEqual(invalid.status_code, 400, invalid.json)
        with self.app.app_context():
            self.assertEqual(ConsumerUnit.query.filter_by(id=uc_id).one().codigo, '000570778003105')
        document = client.put(f'/api/v1/ucs/{uc_id}', headers=headers, json={'documento': '529.982.247-25'})
        self.assertEqual(document.status_code, 200, document.json)
        self.assertEqual(document.json['data']['documento'], '52998224725')
        bad_document = client.put(f'/api/v1/ucs/{uc_id}', headers=headers, json={'documento': '111.111.111-11'})
        self.assertEqual(bad_document.status_code, 400, bad_document.json)
        for code in (None, 123):
            malformed = client.post('/api/v1/ucs', headers=headers, json={
                'clienteId': 1, 'codigo': code, 'concessionaria': 'Copel',
            })
            self.assertEqual(malformed.status_code, 400, malformed.json)
        inherited = client.post('/api/v1/ucs', headers=headers, json={
            'clienteId': 1, 'codigo': '000000000002', 'concessionaria': None,
        })
        self.assertEqual(inherited.status_code, 201, inherited.json)
        self.assertEqual(inherited.json['data']['codigo'], '000000000000002')
        with self.app.app_context():
            legacy = ConsumerUnit(empresa_id=1, client_id=1, codigo='000000000003', concessionaria='Copel')
            db.session.add(legacy)
            db.session.commit()
            legacy_id = legacy.id
        untouched = client.put(f'/api/v1/ucs/{legacy_id}', headers=headers, json={
            'codigo': '000000000003', 'concessionaria': 'Copel', 'apelido': 'Sem migrar',
        })
        self.assertEqual(untouched.status_code, 200, untouched.json)
        self.assertEqual(untouched.json['data']['codigo'], '000000000003')

    def test_nested_client_edit_cannot_take_another_clients_uc(self):
        with self.app.app_context():
            db.session.add(ConsumerUnit(empresa_id=1, client_id=3, codigo='000000000000005'))
            db.session.commit()
            foreign_id = ConsumerUnit.query.filter_by(client_id=3).one().id
        response = self.app.test_client().put('/api/v1/clients/1',
            headers={'Authorization': f'Bearer {self._token("owner@a.test")}'},
            json={'email': 'a@test.local', 'ucs': [{'id': foreign_id, 'codigo': '000000000000005'}]})
        self.assertEqual(response.status_code, 404, response.json)

    def test_duplicate_client_cpf_returns_conflict(self):
        client = self.app.test_client()
        headers = {'Authorization': f'Bearer {self._token("owner@a.test")}' }
        payload = {'nome': 'Primeiro', 'cpf': '52998224725', 'email': 'primeiro@test.local'}
        first = client.post('/api/v1/clients', headers=headers, json=payload)
        self.assertEqual(first.status_code, 201, first.json)
        duplicate = client.post('/api/v1/clients', headers=headers, json={**payload, 'nome': 'Segundo'})
        self.assertEqual(duplicate.status_code, 409, duplicate.json)
        with self.app.app_context():
            Client.query.filter_by(cpf='52998224725').delete()
            db.session.commit()

    @classmethod
    def setUpClass(cls):
        uri = f"sqlite:///{_DB.name.replace(chr(92), '/')}"
        cls.prepare_test_runtime(uri, 'fatura-upload-test', limiter_enabled=False)
        cls.app = create_app()
        with cls.app.app_context():
            db.create_all()
            db.session.add_all([
                Empresa(id=1, nome='Empresa A', slug='f2-a'),
                Empresa(id=2, nome='Empresa B', slug='f2-b'),
                Client(id=1, empresa_id=1, nome='Cliente A', cpf='11111111111', email='a@test.local'),
                Client(id=2, empresa_id=2, nome='Cliente B', cpf='22222222222', email='b@test.local'),
                Client(id=3, empresa_id=1, nome='Cliente A2', cpf='33333333333', email='a2@test.local'),
            ])
            db.session.add_all([
                User(empresa_id=1, nome=role, email=f'{role}@a.test', password_hash='x', role=role)
                for role in ('owner', 'admin', 'financial', 'operator', 'viewer')
            ])
            db.session.add(User(
                empresa_id=2, nome='Owner B', email='owner@b.test', password_hash='x', role='owner',
            ))
            db.session.add(User(
                empresa_id=1, nome='Platform', email='platform@a.test', password_hash='x',
                role='viewer', is_platform_admin=True,
            ))
            db.session.commit()
            cls.user_ids = {
                user.email: user.id for user in db.session.execute(db.select(User)).scalars()
            }

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        os.unlink(_DB.name)
        cls.restore_test_runtime()

    def setUp(self):
        self.drive = FakeDrive()
        self.drive_patch = patch('services.document_service.get_drive_service', return_value=self.drive)
        self.drive_patch.start()
        self.store = FakeObjectStore()
        self.store_patch = patch.object(upload_service, 'get_object_storage', return_value=self.store)
        self.store_patch.start()
        self.read_store_patch = patch('services.invoice_document_service.get_object_storage',
            return_value=self.store)
        self.read_store_patch.start()

    def tearDown(self):
        self.drive_patch.stop()
        self.store_patch.stop()
        self.read_store_patch.stop()
        with self.app.app_context():
            FaturaConcessionaria.query.delete()
            Document.query.delete()
            ConsumerUnit.query.delete()
            db.session.commit()

    @staticmethod
    def _pdf(pages=1, encrypted=False):
        writer = PdfWriter()
        for _ in range(pages):
            writer.add_blank_page(width=72, height=72)
        if encrypted:
            writer.encrypt('segredo')
        output = io.BytesIO()
        writer.write(output)
        return output.getvalue()

    def _token(self, email):
        with self.app.app_context():
            return generate_token(self.user_ids[email])

    def _upload(self, body, filename='fatura.pdf', mime='application/pdf', email='owner@a.test', client_id=1):
        return self.app.test_client().post(
            f'/api/v1/clients/{client_id}/invoices/upload',
            headers={'Authorization': f'Bearer {self._token(email)}'},
            data={'arquivo': (io.BytesIO(body), filename, mime)},
            content_type='multipart/form-data',
        )

    def _upload_auto(self, body, email='owner@a.test', path='/api/v1/billing-calculations/invoices/upload'):
        return self.app.test_client().post(
            path, headers={'Authorization': f'Bearer {self._token(email)}'},
            data={'arquivo': (io.BytesIO(body), 'fatura.pdf', 'application/pdf')},
            content_type='multipart/form-data',
        )

    def test_auto_upload_links_client_from_unique_documentary_uc(self):
        with self.app.app_context():
            db.session.add(ConsumerUnit(empresa_id=1, client_id=1, codigo='000000000000001',
                                        codigo_aneel='570778003105'))
            db.session.commit()
        response = self._upload_auto(make_pdf())
        self.assertEqual(response.status_code, 201, response.json)
        with self.app.app_context():
            invoice = FaturaConcessionaria.query.one()
            document = Document.query.one()
            self.assertEqual((invoice.empresa_id, invoice.client_id, document.client_id), (1, 1, 1))
            self.assertIsNone(invoice.consumer_unit_id)

    def test_general_document_upload_falls_back_when_oauth_token_cannot_be_decrypted(self):
        with self.app.app_context():
            db.session.add(ConsumerUnit(empresa_id=1, client_id=1, codigo='000000000000001'))
            db.session.add(GoogleAccount(empresa_id=1, email='broken@test.local',
                                         is_active=True, refresh_token_encrypted='invalid'))
            db.session.commit()
        self.drive_patch.stop()
        drive_service.invalidate_drive_cache(1)
        try:
            with patch('services.document_service.get_drive_service', side_effect=drive_service.get_drive_service), \
                 patch.object(drive_service, '_build_service_account_credentials', side_effect=FileNotFoundError):
                unavailable = self.app.test_client().post('/api/v1/documents',
                    headers={'Authorization': f'Bearer {self._token("owner@a.test")}'},
                    data={'clienteId': '1', 'arquivo': (io.BytesIO(make_pdf()), 'legacy.pdf', 'application/pdf')},
                    content_type='multipart/form-data')
            self.assertEqual(unavailable.status_code, 503)
            with self.app.app_context():
                self.assertEqual((Document.query.count(), FaturaConcessionaria.query.count()), (0, 0))
            with patch('services.document_service.get_drive_service', side_effect=drive_service.get_drive_service), \
                 patch.object(drive_service, '_build_service_account_credentials', return_value=object()), \
                 patch.object(drive_service, '_resolve_tenant_root_folder_id', return_value='test-root'), \
                 patch.object(drive_service, 'GoogleDriveService', return_value=self.drive):
                response = self.app.test_client().post('/api/v1/documents',
                    headers={'Authorization': f'Bearer {self._token("owner@a.test")}'},
                    data={'clienteId': '1', 'arquivo': (io.BytesIO(make_pdf()), 'legacy.pdf', 'application/pdf')},
                    content_type='multipart/form-data')
            self.assertEqual(response.status_code, 201, response.json)
            with self.app.app_context():
                self.assertEqual((Document.query.count(), FaturaConcessionaria.query.count()), (1, 0))
        finally:
            drive_service.invalidate_drive_cache(1)
            self.drive_patch.start()
            with self.app.app_context():
                GoogleAccount.query.filter_by(email='broken@test.local').delete()
                db.session.commit()

    def test_auto_upload_never_uses_uc_from_another_tenant(self):
        with self.app.app_context():
            db.session.add(ConsumerUnit(empresa_id=2, client_id=2, codigo='000000000000001'))
            db.session.commit()
        response = self._upload_auto(make_pdf())
        self.assertEqual((response.status_code, response.json['code']), (422, 'UC_NOT_FOUND'))
        with self.app.app_context():
            self.assertEqual((Document.query.count(), FaturaConcessionaria.query.count()), (0, 0))

    def test_auto_upload_matches_legacy_copel_twelve_digits(self):
        with self.app.app_context():
            db.session.add(ConsumerUnit(empresa_id=1, client_id=1, codigo='000000000001'))
            db.session.commit()
        response = self._upload_auto(make_pdf())
        self.assertEqual(response.status_code, 201, response.json)

    def test_auto_upload_normalizes_twelve_digit_documentary_uc(self):
        with self.app.app_context():
            db.session.add(ConsumerUnit(empresa_id=1, client_id=1, codigo='000000000000001', concessionaria='Copel'))
            db.session.commit()
        response = self._upload_auto(make_pdf(changes={'uc': '000000000001'}))
        self.assertEqual(response.status_code, 201, response.json)

    def test_auto_upload_preserves_ambiguity_between_legacy_and_canonical_codes(self):
        with self.app.app_context():
            db.session.add_all([
                ConsumerUnit(empresa_id=1, client_id=1, codigo='000000000001', concessionaria='Copel'),
                ConsumerUnit(empresa_id=1, client_id=3, codigo='000000000000001', concessionaria='Copel'),
            ])
            db.session.commit()
        response = self._upload_auto(make_pdf())
        self.assertEqual((response.status_code, response.json['code']), (409, 'UC_MATCH_AMBIGUOUS'))

    def test_auto_upload_uses_only_canonical_uc_code(self):
        with self.app.app_context():
            db.session.add(ConsumerUnit(empresa_id=1, client_id=1, codigo='570778003105',
                                        codigo_aneel='000000000000001'))
            db.session.commit()
        response = self._upload_auto(make_pdf(), email='platform@a.test',
                                     path='/api/v1/platform/empresas/1/billing-calculations/invoices/upload')
        self.assertEqual(response.status_code, 422, response.json)
        self.assertEqual(response.json, {
            'code': 'UC_NOT_FOUND', 'error': 'UC da fatura nao encontrada nesta empresa.',
        })
        with self.app.app_context():
            self.assertEqual((Document.query.count(), FaturaConcessionaria.query.count()), (0, 0))

    def test_auto_upload_rejects_ambiguous_uc_without_storage(self):
        with self.app.app_context():
            db.session.add_all([
                ConsumerUnit(empresa_id=1, client_id=1, codigo='000000000000001'),
                ConsumerUnit(empresa_id=1, client_id=3, codigo='000000000000001'),
            ])
            db.session.commit()
        response = self._upload_auto(make_pdf())
        self.assertEqual((response.status_code, response.json['code']), (409, 'UC_MATCH_AMBIGUOUS'))
        with self.app.app_context():
            self.assertEqual((Document.query.count(), FaturaConcessionaria.query.count()), (0, 0))
        self.assertEqual(self.store.files, {})

    def test_auto_upload_rejects_unreadable_uc_and_unknown_layout(self):
        unreadable = self._upload_auto(make_pdf(changes={'uc': '000000000000001 000000000000002'}))
        self.assertEqual((unreadable.status_code, unreadable.json['code']), (422, 'UC_CODE_UNREADABLE'))
        unknown = self._upload_auto(self._pdf())
        self.assertEqual((unknown.status_code, unknown.json['code']), (422, 'INVOICE_LAYOUT_UNSUPPORTED'))
        with self.app.app_context():
            self.assertEqual((Document.query.count(), FaturaConcessionaria.query.count()), (0, 0))

    def test_auto_upload_rbac_duplicate_and_platform_company_selection(self):
        with self.app.app_context():
            db.session.add_all([
                ConsumerUnit(empresa_id=1, client_id=1, codigo='000000000000001'),
                ConsumerUnit(empresa_id=2, client_id=2, codigo='000000000000001'),
            ])
            db.session.commit()
        body = make_pdf()
        for role in ('operator', 'viewer'):
            self.assertEqual(self._upload_auto(body, email=f'{role}@a.test').status_code, 403)
        first = self._upload_auto(body)
        repeated = self._upload_auto(body)
        self.assertEqual((first.status_code, repeated.status_code), (201, 200))
        self.assertTrue(repeated.json['data']['duplicate'])
        platform_path = '/api/v1/platform/empresas/2/billing-calculations/invoices/upload'
        self.assertEqual(self._upload_auto(body, path=platform_path).status_code, 403)
        platform = self._upload_auto(body, email='platform@a.test', path=platform_path)
        self.assertEqual(platform.status_code, 201, platform.json)
        with self.app.app_context():
            own = FaturaConcessionaria.query.filter_by(empresa_id=1).one()
            other = FaturaConcessionaria.query.filter_by(empresa_id=2).one()
            self.assertEqual((own.client_id, other.client_id), (1, 2))

    def test_auto_upload_rejects_legacy_duplicate_linked_to_wrong_client(self):
        body = make_pdf()
        with self.app.app_context():
            db.session.add(ConsumerUnit(empresa_id=1, client_id=3, codigo='000000000000001'))
            db.session.commit()
        legacy = self._upload(body, client_id=1)
        self.assertEqual(legacy.status_code, 201)
        automatic = self._upload_auto(body)
        self.assertEqual((automatic.status_code, automatic.json['code']), (409, 'INVOICE_CLIENT_CONFLICT'))
        with self.app.app_context():
            invoice = FaturaConcessionaria.query.one()
            self.assertEqual((invoice.client_id, Document.query.one().client_id), (1, 1))
        self.assertEqual(len(self.store.files), 1)

    def test_valid_pdf_creates_document_and_immutable_source(self):
        body = self._pdf()
        response = self._upload(body, filename='../../fatura original.pdf')
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.json['data']['duplicate'])

        with self.app.app_context():
            invoice = FaturaConcessionaria.query.one()
            document = Document.query.one()
            self.assertEqual(invoice.document_id, document.id)
            self.assertEqual(invoice.client_id, 1)
            self.assertIsNone(invoice.consumer_unit_id)
            self.assertEqual(invoice.arquivo_hash, hashlib.sha256(body).hexdigest())
            self.assertEqual((invoice.status_extracao, invoice.status_validacao), ('recebida', 'pendente'))
            self.assertEqual((document.mime_type, document.storage_provider), ('application/pdf', 's3'))
            self.assertRegex(document.storage_ref, r'^tenants/1/invoices/\d{4}/\d{2}/[0-9a-f]{32}\.pdf$')
            self.assertEqual(document.nome, 'fatura_original.pdf')

    def test_existing_document_upload_flow_still_commits(self):
        response = self.app.test_client().post(
            '/api/v1/documents',
            headers={'Authorization': f"Bearer {self._token('owner@a.test')}"},
            data={
                'clienteId': '1',
                'arquivo': (io.BytesIO(self._pdf()), 'documento.pdf', 'application/pdf'),
            },
            content_type='multipart/form-data',
        )
        self.assertEqual(response.status_code, 201)
        with self.app.app_context():
            self.assertEqual(Document.query.count(), 1)
            self.assertEqual(FaturaConcessionaria.query.count(), 0)

    def test_invalid_extension_mime_magic_corruption_and_empty_are_controlled(self):
        cases = [
            (self._pdf(), 'fatura.txt', 'application/pdf', 'INVALID_FILE_TYPE'),
            (self._pdf(), 'fatura.pdf', 'text/plain', 'INVALID_FILE_TYPE'),
            (b'nao e pdf', 'fatura.pdf', 'application/pdf', 'INVALID_PDF'),
            (b'%PDF-1.4\ncorrompido', 'fatura.pdf', 'application/pdf', 'INVALID_PDF'),
            (b'', 'fatura.pdf', 'application/pdf', 'INVALID_PDF'),
        ]
        for body, filename, mime, code in cases:
            with self.subTest(filename=filename, mime=mime, body=body[:10]):
                response = self._upload(body, filename, mime)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json['code'], code)
        with self.app.app_context():
            self.assertEqual((Document.query.count(), FaturaConcessionaria.query.count()), (0, 0))

    def test_exactly_one_file_is_required(self):
        token = self._token('owner@a.test')
        response = self.app.test_client().post(
            '/api/v1/clients/1/invoices/upload',
            headers={'Authorization': f'Bearer {token}'},
            data={'arquivo': [
                (io.BytesIO(self._pdf()), 'uma.pdf', 'application/pdf'),
                (io.BytesIO(self._pdf()), 'duas.pdf', 'application/pdf'),
            ]},
            content_type='multipart/form-data',
        )
        self.assertEqual((response.status_code, response.json['code']), (400, 'INVALID_PDF'))

    def test_encrypted_size_and_page_limits_are_controlled(self):
        encrypted = self._upload(self._pdf(encrypted=True))
        self.assertEqual((encrypted.status_code, encrypted.json['code']), (400, 'PDF_ENCRYPTED'))

        old_bytes = self.app.config['FATURA_CONCESSIONARIA_MAX_BYTES']
        old_pages = self.app.config['FATURA_CONCESSIONARIA_MAX_PAGES']
        try:
            self.app.config['FATURA_CONCESSIONARIA_MAX_BYTES'] = 20
            too_large = self._upload(self._pdf())
            self.assertEqual((too_large.status_code, too_large.json['code']), (413, 'FILE_TOO_LARGE'))
            self.app.config['FATURA_CONCESSIONARIA_MAX_BYTES'] = old_bytes
            self.app.config['FATURA_CONCESSIONARIA_MAX_PAGES'] = 1
            too_many = self._upload(self._pdf(pages=2))
            self.assertEqual((too_many.status_code, too_many.json['code']), (400, 'PDF_TOO_MANY_PAGES'))
        finally:
            self.app.config['FATURA_CONCESSIONARIA_MAX_BYTES'] = old_bytes
            self.app.config['FATURA_CONCESSIONARIA_MAX_PAGES'] = old_pages

    def test_sequential_duplicate_reuses_oldest_without_new_document(self):
        body = self._pdf()
        first = self._upload(body)
        second = self._upload(body, filename='segunda-via.pdf')
        self.assertEqual((first.status_code, second.status_code), (201, 200))
        self.assertTrue(second.json['data']['duplicate'])
        self.assertEqual(second.json['data']['invoiceId'], first.json['data']['invoiceId'])
        with self.app.app_context():
            self.assertEqual((Document.query.count(), FaturaConcessionaria.query.count()), (1, 1))
        self.assertEqual(len(self.store.files), 1)

    def test_tenant_and_financial_permissions_are_enforced(self):
        body = self._pdf()
        hidden = self._upload(body, email='owner@a.test', client_id=2)
        self.assertEqual((hidden.status_code, hidden.json['code']), (404, 'CLIENT_NOT_FOUND'))
        for role in ('operator', 'viewer'):
            denied = self._upload(body, email=f'{role}@a.test')
            self.assertEqual(denied.status_code, 403)
        for role in ('owner', 'admin', 'financial'):
            response = self._upload(body, email=f'{role}@a.test')
            self.assertIn(response.status_code, (200, 201))

    def test_same_hash_does_not_cross_tenants(self):
        body = self._pdf()
        tenant_b = self._upload(body, email='owner@b.test', client_id=2)
        tenant_a = self._upload(body)
        self.assertEqual((tenant_b.status_code, tenant_a.status_code), (201, 201))
        self.assertNotEqual(tenant_b.json['data']['invoiceId'], tenant_a.json['data']['invoiceId'])
        with self.app.app_context():
            self.assertEqual(FaturaConcessionaria.query.count(), 2)

    def test_new_s3_download_checks_tenant_platform_link_hash_and_filename(self):
        body = self._pdf()
        created = self._upload(body, filename='fatura.pdf')
        self.assertEqual(created.status_code, 201, created.json)
        invoice_id = created.json['data']['invoiceId']
        with self.app.app_context():
            invoice = db.session.get(FaturaConcessionaria, invoice_id)
            invoice.competencia = '2026-09'
            invoice.data_vencimento = date(2026, 10, 5)
            document_id = invoice.document_id
            key = invoice.document.storage_ref
            db.session.commit()
        tenant_url = f'/api/v1/billing-calculations/invoices/{invoice_id}/download'
        platform_url = f'/api/v1/platform/empresas/1/billing-calculations/invoices/{invoice_id}/download'
        def get(url, email):
            return self.app.test_client().get(url,
                headers={'Authorization': f'Bearer {self._token(email)}'})
        response = get(tenant_url, 'owner@a.test')
        self.assertEqual((response.status_code, response.data), (200, body))
        self.assertIn('Cliente_A_2026-09_Vencimento_2026-10-05.pdf', response.headers['Content-Disposition'])
        self.assertEqual(get(tenant_url, 'owner@b.test').status_code, 404)
        self.assertEqual(get(tenant_url, 'financial@a.test').status_code, 200)
        self.assertEqual(get(tenant_url, 'platform@a.test').status_code, 403)
        self.assertEqual(get(platform_url, 'owner@a.test').status_code, 403)
        self.assertEqual(get(platform_url, 'platform@a.test').status_code, 200)
        self.assertEqual(get(f'/api/v1/platform/empresas/2/billing-calculations/invoices/{invoice_id}/download',
                             'platform@a.test').status_code, 404)
        generic = get(f'/api/v1/documents/{document_id}/download', 'owner@a.test')
        self.assertEqual(generic.status_code, 302)
        self.assertIn(tenant_url, generic.headers['Location'])
        platform_client = self.app.test_client()
        admin_headers = {'Authorization': f'Bearer {self._token("platform@a.test")}' }
        without_selection = platform_client.get(f'/api/v1/documents/{document_id}/download',
            headers=admin_headers)
        self.assertEqual(without_selection.status_code, 403)
        platform_client.set_cookie('hub_platform_view', '1')
        selected = platform_client.get(f'/api/v1/documents/{document_id}/download',
            headers=admin_headers)
        self.assertEqual(selected.status_code, 302)
        self.assertIn(platform_url, selected.headers['Location'])
        listed = get('/api/v1/billing-calculations/invoices', 'owner@a.test')
        self.assertTrue(listed.json['data'][0]['documentoDisponivel'])
        self.store.files[key] = b'%PDF-tampered'
        corrupted = get(tenant_url, 'owner@a.test')
        self.assertEqual((corrupted.status_code, corrupted.json['code']),
                         (503, 'DOCUMENT_STORAGE_UNAVAILABLE'))

    def test_invoice_document_from_other_tenant_is_never_read(self):
        uploaded = self._upload(self._pdf())
        invoice_id = uploaded.json['data']['invoiceId']
        with self.app.app_context():
            Document.query.one().empresa_id = 2
            db.session.commit()
        response = self.app.test_client().get(
            f'/api/v1/billing-calculations/invoices/{invoice_id}/download',
            headers={'Authorization': f'Bearer {self._token("owner@a.test")}'})
        self.assertEqual(response.status_code, 404)

    def test_legacy_drive_invoice_remains_downloadable(self):
        body = self._pdf()
        self.drive.files['file-legacy'] = {'bytes': body, 'name': 'old.pdf',
            'mime': 'application/pdf', 'md5': hashlib.md5(body).hexdigest()}
        with self.app.app_context():
            document = Document(empresa_id=1, client_id=1, nome='old.pdf',
                storage_provider='google_drive', storage_ref='file-legacy', mime_type='application/pdf')
            db.session.add(document)
            db.session.flush()
            invoice = FaturaConcessionaria(empresa_id=1, client_id=1,
                document_id=document.id, arquivo_hash=hashlib.sha256(body).hexdigest())
            db.session.add(invoice)
            db.session.commit()
            invoice_id, document_id = invoice.id, document.id
        with patch('services.invoice_document_service.get_object_storage',
                   side_effect=lambda provider: LegacyDriveObjectStorage()
                   if provider == 'google_drive' else self.store), \
                patch('services.drive_service.get_drive_service', return_value=self.drive):
            response = self.app.test_client().get(
                f'/api/v1/billing-calculations/invoices/{invoice_id}/download',
                headers={'Authorization': f'Bearer {self._token("owner@a.test")}'})
        self.assertEqual((response.status_code, response.data), (200, body))
        hidden = self.app.test_client().get(
            f'/api/v1/billing-calculations/invoices/{invoice_id}/download',
            headers={'Authorization': f'Bearer {self._token("owner@b.test")}'})
        self.assertEqual(hidden.status_code, 404)
        generic = self.app.test_client().get(f'/api/v1/documents/{document_id}/download',
            headers={'Authorization': f'Bearer {self._token("owner@a.test")}'})
        self.assertEqual(generic.status_code, 302)
        self.assertIn('drive.google.com', generic.headers['Location'])

    def test_legacy_local_invoice_remains_downloadable(self):
        from services import document_service
        body = self._pdf()
        with tempfile.TemporaryDirectory() as folder, patch.object(document_service, 'UPLOAD_ROOT', Path(folder)):
            (Path(folder) / 'old.pdf').write_bytes(body)
            with self.app.app_context():
                document = Document(empresa_id=1, client_id=1, nome='old.pdf',
                    storage_provider='local', storage_ref='old.pdf', mime_type='application/pdf')
                db.session.add(document)
                db.session.flush()
                invoice = FaturaConcessionaria(empresa_id=1, client_id=1,
                    document_id=document.id, arquivo_hash=hashlib.sha256(body).hexdigest())
                db.session.add(invoice)
                db.session.commit()
                invoice_id = invoice.id
            response = self.app.test_client().get(
                f'/api/v1/billing-calculations/invoices/{invoice_id}/download',
                headers={'Authorization': f'Bearer {self._token("owner@a.test")}'})
            self.assertEqual((response.status_code, response.data), (200, body))

    def test_storage_failure_prevents_invoice_commit(self):
        with patch.object(self.store, 'put', side_effect=RuntimeError('unavailable')):
            response = self._upload(self._pdf())
        self.assertEqual((response.status_code, response.json['code']),
                         (503, 'DOCUMENT_STORAGE_UNAVAILABLE'))
        with self.app.app_context():
            self.assertEqual((Document.query.count(), FaturaConcessionaria.query.count()), (0, 0))

    def test_local_development_upload_download_roundtrip(self):
        body = self._pdf()
        with tempfile.TemporaryDirectory() as folder:
            storage = LocalObjectStorage(Path(folder))
            with patch.object(upload_service, 'get_object_storage', return_value=storage), \
                 patch('services.invoice_document_service.get_object_storage', return_value=storage):
                uploaded = self._upload(body)
                self.assertEqual(uploaded.status_code, 201, uploaded.json)
                invoice_id = uploaded.json['data']['invoiceId']
                with self.app.app_context():
                    document = Document.query.one()
                    self.assertEqual(document.storage_provider, 'local')
                    self.assertTrue((Path(folder) / document.storage_ref).exists())
                response = self.app.test_client().get(
                    f'/api/v1/billing-calculations/invoices/{invoice_id}/download',
                    headers={'Authorization': f'Bearer {self._token("owner@a.test")}'})
                self.assertEqual((response.status_code, response.data), (200, body))
                generic = self.app.test_client().get(
                    f'/api/v1/documents/{document.id}/download',
                    headers={'Authorization': f'Bearer {self._token("owner@a.test")}'})
                self.assertEqual(generic.status_code, 302)

    def test_failure_after_storage_cleans_new_remote_file_and_database_rows(self):
        with patch.object(upload_service.db.session, 'commit', side_effect=RuntimeError('falha controlada')):
            response = self._upload(self._pdf())
        self.assertEqual((response.status_code, response.json['code']), (503, 'DOCUMENT_STORAGE_UNAVAILABLE'))
        self.assertEqual(len(self.store.deleted), 1)
        self.assertEqual(self.store.files, {})
        with self.app.app_context():
            self.assertEqual((Document.query.count(), FaturaConcessionaria.query.count()), (0, 0))

    def test_concurrent_duplicate_returns_idempotently_and_cleans_loser(self):
        body = self._pdf()
        barrier = threading.Barrier(2)
        original_put = self.store.put

        def synchronized_put(*args, **kwargs):
            result = original_put(*args, **kwargs)
            barrier.wait(timeout=5)
            return result

        token = self._token('owner@a.test')

        def request_upload():
            return self.app.test_client().post(
                '/api/v1/clients/1/invoices/upload',
                headers={'Authorization': f'Bearer {token}'},
                data={'arquivo': (io.BytesIO(body), 'concorrente.pdf', 'application/pdf')},
                content_type='multipart/form-data',
            )

        with patch.object(self.store, 'put', side_effect=synchronized_put):
            with ThreadPoolExecutor(max_workers=2) as executor:
                responses = list(executor.map(lambda _: request_upload(), range(2)))

        self.assertEqual(sorted(response.status_code for response in responses), [200, 201])
        self.assertEqual(sum(response.json['data']['duplicate'] for response in responses), 1)
        with self.app.app_context():
            self.assertEqual((Document.query.count(), FaturaConcessionaria.query.count()), (1, 1))
        self.assertEqual(len(self.store.files), 1)


if __name__ == '__main__':
    unittest.main()
