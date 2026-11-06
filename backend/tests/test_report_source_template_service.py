"""Template de ORIGEM do relatorio, por categoria (documento/planilha/
apresentacao): a empresa aponta um arquivo proprio do Google Drive (precisa
de conta Google ativa) ou sobe um arquivo office com o marcador {{TABELA}}
-- cobre validacao, troca de origem e isolamento de tenant (empresa nunca
ve/usa a config de outra)."""
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

_DATABASE_FILE = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_DATABASE_FILE.close()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from docx import Document as DocxDocument  # noqa: E402
from openpyxl import Workbook  # noqa: E402
from pptx import Presentation  # noqa: E402
from flask import g  # noqa: E402
from unittest.mock import patch  # noqa: E402

from app import create_app  # noqa: E402
from extensions import db  # noqa: E402
from models.document import Document  # noqa: E402
from models.empresa import Empresa  # noqa: E402
from models.google_account import GoogleAccount  # noqa: E402
from models.setting import Setting  # noqa: E402
from services import report_source_template_service as svc  # noqa: E402
from services.google_report_renderers import MARCADOR_TABELA  # noqa: E402
try:
    from .support import IsolatedTestRuntime  # noqa: E402
except ImportError:
    from support import IsolatedTestRuntime  # noqa: E402


def _docx_bytes(paragrafos: list[str]) -> bytes:
    documento = DocxDocument()
    for texto in paragrafos:
        documento.add_paragraph(texto)
    buffer = io.BytesIO()
    documento.save(buffer)
    return buffer.getvalue()


def _xlsx_bytes(linhas: list[list[str]]) -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    for linha in linhas:
        worksheet.append(linha)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _pptx_bytes(texto_shape: str | None) -> bytes:
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[5])
    if texto_shape is not None:
        caixa = slide.shapes.add_textbox(0, 0, 100, 100)
        caixa.text_frame.text = texto_shape
    buffer = io.BytesIO()
    presentation.save(buffer)
    return buffer.getvalue()


# categoria -> (extensao, mimeGoogle, bytes_com_marcador, bytes_sem_marcador, bytes_extensao_errada_nome)
_FIXTURES = {
    'documento': {
        'extensao': '.docx',
        'mime_google': 'application/vnd.google-apps.document',
        'com_marcador': lambda: _docx_bytes(['Marca da empresa', MARCADOR_TABELA]),
        'sem_marcador': lambda: _docx_bytes(['Sem marcador aqui']),
    },
    'planilha': {
        'extensao': '.xlsx',
        'mime_google': 'application/vnd.google-apps.spreadsheet',
        'com_marcador': lambda: _xlsx_bytes([['A', MARCADOR_TABELA]]),
        'sem_marcador': lambda: _xlsx_bytes([['A', 'B']]),
    },
    'apresentacao': {
        'extensao': '.pptx',
        'mime_google': 'application/vnd.google-apps.presentation',
        'com_marcador': lambda: _pptx_bytes(MARCADOR_TABELA),
        'sem_marcador': lambda: _pptx_bytes('Sem marcador'),
    },
}


class FakeFileStorage:
    def __init__(self, filename: str, content: bytes, mimetype='application/octet-stream'):
        self.filename = filename
        self.mimetype = mimetype
        self.stream = io.BytesIO(content)

    def read(self, *args):
        return self.stream.read(*args)


class FakeObjectStore:
    provider = 's3'

    def __init__(self):
        self.files: dict[str, bytes] = {}

    def put(self, key, data, content_type):
        self.files[key] = data

    def read(self, key, max_bytes):
        return self.files[key][:max_bytes + 1]

    def delete(self, key):
        self.files.pop(key, None)


class FakeDriveService:
    def __init__(self, item_by_id: dict):
        self._item_by_id = item_by_id

    def get_authorized_item(self, item_id: str) -> dict:
        item = self._item_by_id.get(item_id)
        if not item:
            raise ValueError('Arquivo do Google Drive nao encontrado.')
        return item


class ReportSourceTemplateServiceTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepare_test_runtime(
            f"sqlite:///{_DATABASE_FILE.name.replace(chr(92), '/')}",
            'report-source-template-test-secret',
        )
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        with cls.app.app_context():
            db.create_all()
            db.session.add_all([Empresa(nome='A', slug='rst-a'), Empresa(nome='B', slug='rst-b')])
            db.session.commit()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        os.unlink(_DATABASE_FILE.name)
        cls.restore_test_runtime()

    def setUp(self):
        self.ctx = self.app.test_request_context('/')
        self.ctx.push()
        g.current_empresa_id = 1
        for model in (Document, GoogleAccount, Setting):
            db.session.query(model).delete()
        db.session.commit()
        self.store = FakeObjectStore()
        self.store_patch = patch('services.document_service.get_object_storage', return_value=self.store)
        self.store_patch.start()

    def tearDown(self):
        self.store_patch.stop()
        db.session.rollback()
        self.ctx.pop()

    def _conectar_google(self, empresa_id: int = 1) -> None:
        db.session.add(GoogleAccount(empresa_id=empresa_id, nome='Conta', email='c@x.test', is_active=True))
        db.session.commit()

    def test_categoria_invalida_levanta_erro(self):
        with self.assertRaises(ValueError):
            svc.get_config('invalida', 1)

    def test_get_config_sem_nada_configurado_para_cada_categoria(self):
        for categoria in _FIXTURES:
            with self.subTest(categoria=categoria):
                self.assertEqual(svc.get_config(categoria, 1), {'tipoOrigem': None, 'driveFileId': None, 'documentoNome': None})

    def test_set_drive_source_sem_conta_google_levanta_erro(self):
        for categoria in _FIXTURES:
            with self.subTest(categoria=categoria):
                with self.assertRaisesRegex(ValueError, 'Nenhuma conta Google'):
                    svc.set_drive_source(categoria, 1, 'file-123')

    def test_set_drive_source_rejeita_mimetype_de_outra_categoria(self):
        self._conectar_google()
        for categoria, fixture in _FIXTURES.items():
            outro_mime = next(f['mime_google'] for cat, f in _FIXTURES.items() if cat != categoria)
            with self.subTest(categoria=categoria):
                drive = FakeDriveService({'file-123': {'mimeType': outro_mime}})
                with patch('services.report_source_template_service.get_drive_service', return_value=drive):
                    with self.assertRaises(ValueError):
                        svc.set_drive_source(categoria, 1, 'file-123')

    def test_set_drive_source_valido_fica_configurado_para_cada_categoria(self):
        self._conectar_google()
        for categoria, fixture in _FIXTURES.items():
            with self.subTest(categoria=categoria):
                drive = FakeDriveService({'file-123': {'mimeType': fixture['mime_google']}})
                with patch('services.report_source_template_service.get_drive_service', return_value=drive):
                    resultado = svc.set_drive_source(categoria, 1, 'file-123')
                self.assertEqual(resultado, {'tipoOrigem': 'drive', 'driveFileId': 'file-123', 'documentoNome': None})
                self.assertEqual(svc.resolve_drive_file_id(categoria, 1), 'file-123')
                svc.remove_source(categoria)

    def test_set_upload_source_rejeita_extensao_errada_para_cada_categoria(self):
        for categoria, fixture in _FIXTURES.items():
            with self.subTest(categoria=categoria):
                arquivo = FakeFileStorage('template.pdf', b'conteudo')
                with self.assertRaisesRegex(ValueError, f"precisa ser um \\{fixture['extensao']}"):
                    svc.set_upload_source(categoria, 1, arquivo)
                self.assertEqual(Document.query.count(), 0)

    def test_set_upload_source_rejeita_sem_marcador_para_cada_categoria(self):
        for categoria, fixture in _FIXTURES.items():
            with self.subTest(categoria=categoria):
                arquivo = FakeFileStorage(f"template{fixture['extensao']}", fixture['sem_marcador']())
                with self.assertRaisesRegex(ValueError, 'marcador'):
                    svc.set_upload_source(categoria, 1, arquivo)
                self.assertEqual(Document.query.count(), 0)

    def test_set_upload_source_valido_salva_e_configura_para_cada_categoria(self):
        for categoria, fixture in _FIXTURES.items():
            with self.subTest(categoria=categoria):
                arquivo = FakeFileStorage(f"template{fixture['extensao']}", fixture['com_marcador']())
                resultado = svc.set_upload_source(categoria, 1, arquivo)
                self.assertEqual(resultado['tipoOrigem'], 'upload')
                dados = svc.resolve_upload_bytes(categoria, 1)
                self.assertIsInstance(dados, bytes)
                self.assertGreater(len(dados), 0)
                svc.remove_source(categoria)

    def test_trocar_de_upload_para_drive_limpa_a_anterior(self):
        fixture = _FIXTURES['documento']
        arquivo = FakeFileStorage('template.docx', fixture['com_marcador']())
        svc.set_upload_source('documento', 1, arquivo)

        self._conectar_google()
        drive = FakeDriveService({'file-999': {'mimeType': fixture['mime_google']}})
        with patch('services.report_source_template_service.get_drive_service', return_value=drive):
            svc.set_drive_source('documento', 1, 'file-999')

        config = svc.get_config('documento', 1)
        self.assertEqual(config, {'tipoOrigem': 'drive', 'driveFileId': 'file-999', 'documentoNome': None})
        self.assertIsNone(svc.resolve_upload_bytes('documento', 1))

    def test_categorias_sao_independentes_entre_si(self):
        # configurar 'documento' nao deve afetar 'planilha'
        arquivo = FakeFileStorage('template.docx', _FIXTURES['documento']['com_marcador']())
        svc.set_upload_source('documento', 1, arquivo)
        self.assertEqual(svc.get_config('planilha', 1)['tipoOrigem'], None)

    def test_remove_source_limpa_as_duas_chaves(self):
        arquivo = FakeFileStorage('template.docx', _FIXTURES['documento']['com_marcador']())
        svc.set_upload_source('documento', 1, arquivo)
        svc.remove_source('documento')
        self.assertEqual(svc.get_config('documento', 1), {'tipoOrigem': None, 'driveFileId': None, 'documentoNome': None})

    def test_empresa_nao_ve_configuracao_de_outra_empresa(self):
        arquivo = FakeFileStorage('template.docx', _FIXTURES['documento']['com_marcador']())
        svc.set_upload_source('documento', 1, arquivo)

        g.current_empresa_id = 2
        self.assertEqual(svc.get_config('documento', 2), {'tipoOrigem': None, 'driveFileId': None, 'documentoNome': None})
        self.assertIsNone(svc.resolve_upload_bytes('documento', 2))


if __name__ == '__main__':
    unittest.main()
