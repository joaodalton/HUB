"""create_document/list_documents aceitam plantId: documento vinculado a uma
usina e GET /api/v1/documents?plantId= filtra por ela, com validacao de
tenant igual a clienteId/ucId (documento nao pode apontar pra Plant de outra
empresa)."""
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
from models.empresa import Empresa  # noqa: E402
from models.client import Client  # noqa: E402
from models.document import Document  # noqa: E402
from models.fatura_concessionaria import FaturaConcessionaria  # noqa: E402
from models.plant import Plant  # noqa: E402
from models.setting import Setting  # noqa: E402
from models.user import User  # noqa: E402
from services.document_service import create_document, list_documents  # noqa: E402
from utils.auth import generate_token  # noqa: E402
try:
    from .support import IsolatedTestRuntime  # noqa: E402
except ImportError:
    from support import IsolatedTestRuntime  # noqa: E402


class FakeDrive:
    root_folder_id = 'test-root'

    def __init__(self):
        self.files = {}
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


class FakeFileStorage:
    def __init__(self, filename='contrato.pdf', content=b'conteudo', mimetype='application/pdf'):
        self.filename = filename
        self.mimetype = mimetype
        self._stream = io.BytesIO(content)

    def read(self):
        return self._stream.read()


class DocumentServiceTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepare_test_runtime(
            f"sqlite:///{_DATABASE_FILE.name.replace(chr(92), '/')}",
            'document-service-test-secret',
        )
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        with cls.app.app_context():
            db.create_all()
            empresa_a = Empresa(nome='A', slug='document-service-a')
            empresa_b = Empresa(nome='B', slug='document-service-b')
            db.session.add_all([empresa_a, empresa_b])
            db.session.flush()
            owner = User(empresa_id=empresa_a.id, nome='Owner', email='owner@document-service.test',
                          password_hash='x', role='owner')
            # Esta suite exercita o fluxo pre-existente (Drive); o padrao
            # da empresa passou a ser 's3' (STORAGE-2) -- fixa explicitamente
            # 'google_drive' pra nao mudar o comportamento testado aqui.
            db.session.add_all([owner, Setting(
                empresa_id=empresa_a.id, chave='document_storage_provider', valor='google_drive')])
            db.session.commit()
            cls.owner_id = owner.id
            cls.empresa_b_id = empresa_b.id

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
        g.current_empresa_id = 1
        db.session.query(Document).delete()
        db.session.query(Plant).delete()
        db.session.commit()
        self.plant = Plant(empresa_id=1, nome='Usina', uc='UC-1', kw_pico=100)
        self.plant_outra_empresa = Plant(empresa_id=self.empresa_b_id, nome='Usina B', uc='UC-2', kw_pico=50)
        db.session.add_all([self.plant, self.plant_outra_empresa])
        db.session.commit()

        self.drive = FakeDrive()
        self.drive_patch = patch('services.document_service.get_drive_service', return_value=self.drive)
        self.drive_patch.start()

    def tearDown(self):
        self.drive_patch.stop()
        db.session.rollback()
        self.ctx.pop()

    def test_create_document_aceita_plant_id(self):
        documento = create_document({'nome': 'Contrato', 'plantId': self.plant.id}, FakeFileStorage())
        self.assertEqual(documento['plantId'], self.plant.id)

    def test_create_document_rejeita_plant_id_de_outra_empresa(self):
        with self.assertRaises(ValueError):
            create_document({'nome': 'Contrato', 'plantId': self.plant_outra_empresa.id}, FakeFileStorage())

    def test_list_documents_filtra_por_plant_id(self):
        create_document({'nome': 'Contrato', 'plantId': self.plant.id}, FakeFileStorage(filename='a.pdf'))
        create_document({'nome': 'Outro', 'plantId': None}, FakeFileStorage(filename='b.pdf'))
        resultado = list_documents(plant_id=self.plant.id)
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]['plantId'], self.plant.id)

    def test_list_documents_oculta_documento_de_fatura_concessionaria(self):
        normal = create_document({'nome': 'Contrato'}, FakeFileStorage(filename='normal.pdf'))
        oculto = create_document({'nome': 'Boleto'}, FakeFileStorage(filename='boleto.pdf'))
        client = Client(empresa_id=1, nome='Cliente', cpf='00000000000', email='c@test.local')
        db.session.add(client)
        db.session.flush()
        db.session.add(FaturaConcessionaria(
            empresa_id=1, client_id=client.id, document_id=oculto['id'], arquivo_hash='hash-1',
        ))
        db.session.commit()

        resultado = list_documents()
        ids = [documento['id'] for documento in resultado]
        self.assertIn(normal['id'], ids)
        self.assertNotIn(oculto['id'], ids)

    def test_get_route_filtra_por_plant_id(self):
        create_document({'nome': 'Contrato', 'plantId': self.plant.id}, FakeFileStorage(filename='c.pdf'))
        create_document({'nome': 'Outro', 'plantId': None}, FakeFileStorage(filename='d.pdf'))
        db.session.commit()

        token = generate_token(self.owner_id)
        resposta = self.app.test_client().get(
            '/api/v1/documents',
            query_string={'plantId': self.plant.id},
            headers={'Authorization': f'Bearer {token}'},
        )
        self.assertEqual(resposta.status_code, 200)
        dados = resposta.get_json()['data']
        self.assertEqual(len(dados), 1)
        self.assertEqual(dados[0]['plantId'], self.plant.id)


if __name__ == '__main__':
    unittest.main()
