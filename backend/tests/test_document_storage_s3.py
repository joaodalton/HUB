"""Documento geral (cliente/UC/usina) no mesmo object storage das faturas
(STORAGE-2). Provider resolvido por Setting('document_storage_provider') da
empresa atual: 's3' por padrao, 'google_drive' se configurado explicitamente
-- ver services/settings_service.py:get_document_storage_provider e
HANDOFFS_PLATFORM_STORAGE.md."""
import hashlib
import io
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

_DATABASE_FILE = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_DATABASE_FILE.close()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flask import g  # noqa: E402

from app import create_app  # noqa: E402
from extensions import db  # noqa: E402
from models.client import Client  # noqa: E402
from models.document import Document  # noqa: E402
from models.empresa import Empresa  # noqa: E402
from models.setting import Setting  # noqa: E402
from models.user import User  # noqa: E402
from services.document_service import (  # noqa: E402
    _s3_context, create_document, delete_document,
)
from services.settings_service import update_settings  # noqa: E402
from utils.auth import generate_token  # noqa: E402
try:
    from .support import IsolatedTestRuntime  # noqa: E402
except ImportError:
    from support import IsolatedTestRuntime  # noqa: E402


class FakeDrive:
    root_folder_id = 'test-root'

    def __init__(self):
        self.files = {}

    def find_duplicate(self, name, md5, _parent):
        return next((fid for fid, item in self.files.items()
                     if item['name'] == name and item['md5'] == md5), None)

    def upload_file(self, file_bytes, name, mime_type, _parent):
        file_id = f'file-{len(self.files) + 1}'
        self.files[file_id] = {'bytes': file_bytes, 'name': name, 'md5': hashlib.md5(file_bytes).hexdigest()}
        return file_id

    def delete_file(self, file_id):
        self.files.pop(file_id, None)


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


class FakeFileStorage:
    def __init__(self, filename='contrato.pdf', content=b'conteudo', mimetype='application/pdf'):
        self.filename = filename
        self.mimetype = mimetype
        self._stream = io.BytesIO(content)

    def read(self, *args):
        return self._stream.read(*args)


class DocumentStorageS3Test(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepare_test_runtime(
            f"sqlite:///{_DATABASE_FILE.name.replace(chr(92), '/')}",
            'document-storage-s3-test-secret',
        )
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        with cls.app.app_context():
            db.create_all()
            empresa_a = Empresa(nome='A', slug='document-storage-s3-a')
            empresa_b = Empresa(nome='B', slug='document-storage-s3-b')
            db.session.add_all([empresa_a, empresa_b])
            db.session.flush()
            cls.empresa_a_id = empresa_a.id
            cls.empresa_b_id = empresa_b.id
            owner_a = User(empresa_id=empresa_a.id, nome='Owner A', email='owner@storage-s3-a.test',
                            password_hash='x', role='owner')
            owner_b = User(empresa_id=empresa_b.id, nome='Owner B', email='owner@storage-s3-b.test',
                            password_hash='x', role='owner')
            client_a = Client(empresa_id=empresa_a.id, nome='Cliente A', cpf='11111111111', email='ca@test.local')
            db.session.add_all([owner_a, owner_b, client_a])
            db.session.commit()
            cls.owner_a_id = owner_a.id
            cls.owner_b_id = owner_b.id
            cls.client_a_id = client_a.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        os.unlink(_DATABASE_FILE.name)
        cls.restore_test_runtime()

    def setUp(self):
        self.ctx = self.app.app_context()
        self.ctx.push()
        g.current_empresa_id = self.empresa_a_id
        db.session.query(Document).delete()
        db.session.query(Setting).delete()
        db.session.commit()

        self.drive = FakeDrive()
        self.drive_patch = patch('services.document_service.get_drive_service', return_value=self.drive)
        self.drive_patch.start()

        self.store = FakeObjectStore()
        self.store_patch = patch('services.document_service.get_object_storage', return_value=self.store)
        self.store_patch.start()

    def tearDown(self):
        self.drive_patch.stop()
        self.store_patch.stop()
        db.session.rollback()
        self.ctx.pop()

    def test_context_order_cliente_uc_usina_geral(self):
        self.assertEqual(_s3_context(5, 9, 3), 'cliente-5')
        self.assertEqual(_s3_context(None, 9, 3), 'uc-9')
        self.assertEqual(_s3_context(None, None, 3), 'usina-3')
        self.assertEqual(_s3_context(None, None, None), 'geral')

    def test_upload_default_provider_is_s3_with_safe_key(self):
        document = create_document({'nome': 'Contrato', 'clienteId': self.client_a_id}, FakeFileStorage())
        self.assertEqual(document['storageProvider'], 's3')
        self.assertRegex(
            document['storageRef'],
            rf'^tenants/{self.empresa_a_id}/documents/cliente-{self.client_a_id}/[0-9a-f]{{32}}\.pdf$')
        self.assertNotIn('Cliente', document['storageRef'])
        self.assertNotIn('11111111111', document['storageRef'])

    def test_upload_explicit_google_drive_provider_unchanged(self):
        update_settings({'document_storage_provider': 'google_drive'})
        document = create_document({'nome': 'Contrato'}, FakeFileStorage())
        self.assertEqual(document['storageProvider'], 'google_drive')
        self.assertIn(document['storageRef'], self.drive.files)

    def test_invalid_setting_value_falls_back_to_s3(self):
        db.session.add(Setting(empresa_id=self.empresa_a_id, chave='document_storage_provider', valor='dropbox'))
        db.session.commit()
        document = create_document({'nome': 'Contrato'}, FakeFileStorage())
        self.assertEqual(document['storageProvider'], 's3')

    def test_dedup_same_hash_same_client_reuses_object(self):
        first = create_document({'nome': 'Contrato', 'clienteId': self.client_a_id}, FakeFileStorage(filename='a.pdf'))
        second = create_document({'nome': 'Copia', 'clienteId': self.client_a_id}, FakeFileStorage(filename='b.pdf'))
        self.assertEqual(first['storageRef'], second['storageRef'])
        self.assertEqual(len(self.store.files), 1)
        self.assertEqual(Document.query.count(), 2)

    def test_two_tenants_different_provider_no_leak(self):
        update_settings({'document_storage_provider': 'google_drive'})
        doc_a = create_document({'nome': 'Contrato A'}, FakeFileStorage())
        self.assertEqual(doc_a['storageProvider'], 'google_drive')

        g.current_empresa_id = self.empresa_b_id
        doc_b = create_document({'nome': 'Contrato B'}, FakeFileStorage())
        self.assertEqual(doc_b['storageProvider'], 's3')
        self.assertIsNone(Setting.query.filter_by(
            empresa_id=self.empresa_b_id, chave='document_storage_provider').first())

    def test_storage_failure_does_not_commit(self):
        with patch.object(self.store, 'put', side_effect=RuntimeError('indisponivel')):
            with self.assertRaises(RuntimeError):
                create_document({'nome': 'Contrato'}, FakeFileStorage())
        self.assertEqual(Document.query.count(), 0)

    def test_commit_failure_cleans_only_current_object(self):
        with patch.object(db.session, 'commit', side_effect=RuntimeError('falha')):
            with self.assertRaises(RuntimeError):
                create_document({'nome': 'Contrato'}, FakeFileStorage())
        self.assertEqual(len(self.store.deleted), 1)
        self.assertEqual(self.store.files, {})
        self.assertEqual(Document.query.count(), 0)

    def test_delete_s3_document_removes_bucket_object(self):
        document = create_document({'nome': 'Contrato'}, FakeFileStorage())
        self.assertTrue(delete_document(document['id']))
        self.assertEqual(self.store.deleted, [document['storageRef']])

    def test_delete_does_not_remove_object_still_shared_by_dedup(self):
        first = create_document({'nome': 'Contrato', 'clienteId': self.client_a_id}, FakeFileStorage(filename='a.pdf'))
        second = create_document({'nome': 'Copia', 'clienteId': self.client_a_id}, FakeFileStorage(filename='b.pdf'))
        delete_document(first['id'])
        self.assertEqual(self.store.deleted, [])
        self.assertIn(first['storageRef'], self.store.files)
        delete_document(second['id'])
        self.assertEqual(self.store.deleted, [first['storageRef']])

    def test_download_s3_rbac_tenant_and_filename(self):
        document = create_document({'nome': 'Contrato Importante.pdf'}, FakeFileStorage())
        client = self.app.test_client()
        token_a = generate_token(self.owner_a_id)
        token_b = generate_token(self.owner_b_id)
        response = client.get(f'/api/v1/documents/{document["id"]}/download',
                               headers={'Authorization': f'Bearer {token_a}'})
        self.assertEqual((response.status_code, response.data), (200, b'conteudo'))
        self.assertIn('Contrato_Importante.pdf', response.headers['Content-Disposition'])
        hidden = client.get(f'/api/v1/documents/{document["id"]}/download',
                             headers={'Authorization': f'Bearer {token_b}'})
        self.assertEqual(hidden.status_code, 404)

    def test_delete_lock_blocks_concurrent_dedup_which_then_sees_row_already_gone(self):
        """TOCTOU, ordem 1: delete_document() trava a linha primeiro (via
        _lock_storage_ref_rows) e so entao decide apagar o objeto do bucket.
        Um dedup concorrente que tentaria reaproveitar essa MESMA linha
        (_lock_dedup_candidate_rows) tem que ESPERAR o commit do delete --
        nunca ler a linha enquanto a decisao de apagar o objeto esta em
        aberto -- e, ao continuar, ver que a linha ja nao existe mais."""
        from services.document_service import _lock_dedup_candidate_rows, _lock_storage_ref_rows

        content = b'conteudo-ordem-1'
        file_hash = hashlib.sha256(content).hexdigest()
        original = create_document({'nome': 'Original', 'clienteId': self.client_a_id},
                                    FakeFileStorage(filename='orig.pdf', content=content))

        dedup_unblocked = threading.Event()
        dedup_saw_row = {}

        def _concurrent_dedup():
            with self.app.app_context():
                g.current_empresa_id = self.empresa_a_id
                _lock_dedup_candidate_rows(self.empresa_a_id, self.client_a_id, file_hash)
                dedup_unblocked.set()
                dedup_saw_row['found'] = Document.query.filter_by(
                    empresa_id=self.empresa_a_id, client_id=self.client_a_id,
                    storage_provider='s3', file_hash=file_hash).first() is not None
                db.session.rollback()

        # Mantem a transacao do delete aberta (sem commit) pra provar que o
        # dedup concorrente so avanca depois que ela termina.
        _lock_storage_ref_rows(original['storageRef'], self.empresa_a_id)
        thread = threading.Thread(target=_concurrent_dedup)
        thread.start()
        thread.join(timeout=0.5)
        self.assertFalse(dedup_unblocked.is_set(), 'dedup nao deveria conseguir travar a linha ainda')

        db.session.delete(Document.query.get(original['id']))
        db.session.commit()

        thread.join(timeout=10)
        self.assertTrue(dedup_unblocked.is_set(), 'dedup deveria ter sido liberado apos o commit do delete')
        self.assertFalse(dedup_saw_row['found'], 'dedup nao deveria mais achar a linha ja apagada')

    def test_dedup_lock_blocks_concurrent_delete_which_then_sees_new_sibling(self):
        """TOCTOU, ordem 2: o dedup do upload trava a linha original primeiro
        e so depois insere o Document novo que reaproveita o storage_ref. Um
        delete_document() concorrente dessa mesma linha original tem que
        ESPERAR esse commit antes de decidir se apaga o objeto -- e, ao
        continuar, ver o sibling novo e NAO apagar o objeto."""
        from services.document_service import _lock_dedup_candidate_rows, _lock_storage_ref_rows

        content = b'conteudo-ordem-2'
        file_hash = hashlib.sha256(content).hexdigest()
        original = create_document({'nome': 'Original', 'clienteId': self.client_a_id},
                                    FakeFileStorage(filename='orig.pdf', content=content))

        delete_unblocked = threading.Event()
        delete_saw_shared = {}

        def _concurrent_delete():
            with self.app.app_context():
                g.current_empresa_id = self.empresa_a_id
                _lock_storage_ref_rows(original['storageRef'], self.empresa_a_id)
                delete_unblocked.set()
                delete_saw_shared['found'] = Document.query.filter(
                    Document.storage_ref == original['storageRef'],
                    Document.id != original['id']).first() is not None
                db.session.rollback()

        # Mantem a transacao do dedup aberta (sem commit) pra provar que o
        # delete concorrente so avanca depois que ela termina.
        _lock_dedup_candidate_rows(self.empresa_a_id, self.client_a_id, file_hash)
        thread = threading.Thread(target=_concurrent_delete)
        thread.start()
        thread.join(timeout=0.5)
        self.assertFalse(delete_unblocked.is_set(), 'delete nao deveria conseguir travar a linha ainda')

        sibling = Document(
            empresa_id=self.empresa_a_id, nome='Copia', client_id=self.client_a_id,
            storage_provider='s3', storage_ref=original['storageRef'],
            mime_type='application/pdf', file_hash=file_hash,
        )
        db.session.add(sibling)
        db.session.commit()

        thread.join(timeout=10)
        self.assertTrue(delete_unblocked.is_set(), 'delete deveria ter sido liberado apos o commit do dedup')
        self.assertTrue(delete_saw_shared['found'], 'delete deveria ver o sibling novo e nao apagar o objeto')

    def test_concurrent_delete_and_dedup_upload_never_orphans_shared_object(self):
        """Fim a fim, corrida real (sem forcar ordem): a invariante tem que
        valer independente de quem travar primeiro -- nenhum Document vivo
        pode apontar pra um objeto ja apagado do bucket."""
        content = b'conteudo-concorrente'

        for _ in range(20):
            db.session.query(Document).delete()
            db.session.commit()
            original = create_document({'nome': 'Original', 'clienteId': self.client_a_id},
                                        FakeFileStorage(filename='orig.pdf', content=content))
            original_id = original['id']

            results = {}

            def _delete():
                with self.app.app_context():
                    g.current_empresa_id = self.empresa_a_id
                    try:
                        results['delete'] = delete_document(original_id)
                    except Exception as exc:  # pragma: no cover - diagnostico de falha do teste
                        results['delete'] = exc

            def _upload_duplicate():
                with self.app.app_context():
                    g.current_empresa_id = self.empresa_a_id
                    try:
                        results['upload'] = create_document(
                            {'nome': 'Copia', 'clienteId': self.client_a_id},
                            FakeFileStorage(filename='dup.pdf', content=content))
                    except Exception as exc:  # pragma: no cover - diagnostico de falha do teste
                        results['upload'] = exc

            threads = [threading.Thread(target=_delete), threading.Thread(target=_upload_duplicate)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=10)

            for key, value in results.items():
                self.assertNotIsInstance(value, Exception, f'{key} falhou: {value}')

            with self.app.app_context():
                g.current_empresa_id = self.empresa_a_id
                vivos = Document.query.filter_by(storage_provider='s3').all()
                for vivo in vivos:
                    self.assertIn(vivo.storage_ref, self.store.files,
                                  'Document vivo aponta pra objeto ja apagado do bucket')

    def test_settings_update_rejects_invalid_provider(self):
        with self.assertRaises(ValueError):
            update_settings({'document_storage_provider': 'dropbox'})

    def test_settings_update_accepts_valid_providers(self):
        update_settings({'document_storage_provider': 's3'})
        update_settings({'document_storage_provider': 'google_drive'})


if __name__ == '__main__':
    unittest.main()
