"""Template de ORIGEM do relatorio, por categoria (documento/planilha/
apresentacao): em vez de gerar o arquivo do zero (ver reports_service.py +
*_report_renderers.py), usa um arquivo que a empresa JA TEM -- um arquivo do
Google Drive dela (precisa estar dentro da pasta raiz do Drive configurada
pro tenant, mesma regra de autorizacao de qualquer outro arquivo vinculado
nesse sistema) ou um arquivo office que ela sobe (guardado no mesmo storage
-- S3 ou Drive -- configurado em Configuracoes > Documentos, reaproveitando
document_service.prepare_document). O arquivo precisa ter o marcador de
texto {{TABELA}} (ver google_report_renderers.MARCADOR_TABELA) em algum
lugar -- e onde a tabela de dados entra.

So guarda REFERENCIA (fileId do Drive, ou id do Document) em Setting -- nunca
duplica o arquivo da empresa em outro lugar."""
import io

from extensions import db
from models.document import Document
from models.google_account import GoogleAccount
from services.document_service import load_s3_document, prepare_document
from services.drive_service import get_drive_service
from services.google_report_renderers import MARCADOR_TABELA
from services.settings_service import get_all_settings, update_settings

_CATEGORIAS = {
    'documento': {
        'mime_google': 'application/vnd.google-apps.document',
        'extensao': '.docx',
        'nome_arquivo': 'Documento',
    },
    'planilha': {
        'mime_google': 'application/vnd.google-apps.spreadsheet',
        'extensao': '.xlsx',
        'nome_arquivo': 'Planilha',
    },
    'apresentacao': {
        'mime_google': 'application/vnd.google-apps.presentation',
        'extensao': '.pptx',
        'nome_arquivo': 'Apresentação',
    },
}


def _config_categoria(categoria: str) -> dict:
    config = _CATEGORIAS.get(categoria)
    if not config:
        raise ValueError(f'Categoria de template invalida: {categoria}.')
    return config


def _chave_drive(categoria: str) -> str:
    return f'report_template_{categoria}_drive_file_id'


def _chave_document(categoria: str) -> str:
    return f'report_template_{categoria}_document_id'


def get_config(categoria: str, empresa_id: int) -> dict:
    """Pra tela de Relatorios mostrar o que esta configurado hoje."""
    _config_categoria(categoria)
    settings = get_all_settings()
    drive_file_id = settings.get(_chave_drive(categoria)) or None
    document_id = settings.get(_chave_document(categoria)) or None

    if drive_file_id:
        return {'tipoOrigem': 'drive', 'driveFileId': drive_file_id, 'documentoNome': None}

    if document_id:
        documento = Document.query.filter_by(id=int(document_id), empresa_id=empresa_id).first()
        if documento:
            return {'tipoOrigem': 'upload', 'driveFileId': None, 'documentoNome': documento.nome}

    return {'tipoOrigem': None, 'driveFileId': None, 'documentoNome': None}


def resolve_drive_file_id(categoria: str, empresa_id: int) -> str | None:
    """Pra reports_service: fileId do arquivo-base do Drive, se for essa a origem configurada."""
    return get_all_settings().get(_chave_drive(categoria)) or None


def resolve_upload_bytes(categoria: str, empresa_id: int) -> bytes | None:
    """Pra reports_service: bytes do arquivo-base office, se for essa a origem configurada."""
    document_id = get_all_settings().get(_chave_document(categoria)) or None
    if not document_id:
        return None
    documento = Document.query.filter_by(id=int(document_id), empresa_id=empresa_id).first()
    if not documento:
        return None
    return _carregar_bytes(documento)


def set_drive_source(categoria: str, empresa_id: int, drive_file_id: str) -> dict:
    config = _config_categoria(categoria)
    drive_file_id = (drive_file_id or '').strip()
    if not drive_file_id:
        raise ValueError('ID do arquivo do Google Drive e obrigatorio.')

    conta = GoogleAccount.query.filter_by(empresa_id=empresa_id, is_active=True).first()
    if not conta:
        raise ValueError('Nenhuma conta Google conectada para esta empresa. Conecte em Configuracoes antes.')

    drive = get_drive_service()
    metadata = drive.get_authorized_item(drive_file_id)
    if metadata.get('mimeType') != config['mime_google']:
        raise ValueError(f"O arquivo informado nao e um {config['nome_arquivo']} do Google.")

    update_settings({_chave_drive(categoria): drive_file_id, _chave_document(categoria): ''})
    return get_config(categoria, empresa_id)


def set_upload_source(categoria: str, empresa_id: int, file_storage) -> dict:
    config = _config_categoria(categoria)
    if not file_storage or not file_storage.filename:
        raise ValueError('Arquivo e obrigatorio.')
    if not file_storage.filename.lower().endswith(config['extensao']):
        raise ValueError(f"O arquivo precisa ser um {config['extensao']}.")

    conteudo = file_storage.read()
    file_storage.stream.seek(0)
    _validar_marcador(categoria, conteudo)

    documento, _ = prepare_document({'nome': f"Template de relatorio - {config['nome_arquivo']}"}, file_storage)
    db.session.commit()

    update_settings({_chave_document(categoria): str(documento.id), _chave_drive(categoria): ''})
    return get_config(categoria, empresa_id)


def remove_source(categoria: str) -> None:
    _config_categoria(categoria)
    update_settings({_chave_drive(categoria): '', _chave_document(categoria): ''})


def _carregar_bytes(documento: Document) -> bytes:
    if documento.storage_provider == 's3':
        dados, _ = load_s3_document(documento)
        return dados
    return get_drive_service().download_file(documento.storage_ref)


def _validar_marcador(categoria: str, conteudo: bytes) -> None:
    if categoria == 'documento':
        _validar_marcador_docx(conteudo)
    elif categoria == 'planilha':
        _validar_marcador_xlsx(conteudo)
    else:
        _validar_marcador_pptx(conteudo)


def _validar_marcador_docx(conteudo: bytes) -> None:
    from docx import Document as DocxDocument  # import tardio: so essa funcao usa, evita ciclo
    try:
        documento = DocxDocument(io.BytesIO(conteudo))
    except Exception as exc:
        raise ValueError('Arquivo invalido -- precisa ser um .docx valido.') from exc
    if not any(MARCADOR_TABELA in paragrafo.text for paragrafo in documento.paragraphs):
        raise ValueError(f'O arquivo precisa ter o marcador {MARCADOR_TABELA} em algum paragrafo (onde a tabela vai entrar).')


def _validar_marcador_xlsx(conteudo: bytes) -> None:
    from openpyxl import load_workbook  # import tardio: so essa funcao usa, evita ciclo
    try:
        workbook = load_workbook(io.BytesIO(conteudo))
    except Exception as exc:
        raise ValueError('Arquivo invalido -- precisa ser um .xlsx valido.') from exc
    encontrado = any(
        cell.value == MARCADOR_TABELA
        for worksheet in workbook.worksheets
        for row in worksheet.iter_rows()
        for cell in row
    )
    if not encontrado:
        raise ValueError(f'O arquivo precisa ter o marcador {MARCADOR_TABELA} em alguma celula (onde a tabela vai entrar).')


def _validar_marcador_pptx(conteudo: bytes) -> None:
    from pptx import Presentation  # import tardio: so essa funcao usa, evita ciclo
    try:
        presentation = Presentation(io.BytesIO(conteudo))
    except Exception as exc:
        raise ValueError('Arquivo invalido -- precisa ser um .pptx valido.') from exc
    encontrado = any(
        shape.has_text_frame and MARCADOR_TABELA in shape.text_frame.text
        for slide in presentation.slides
        for shape in slide.shapes
    )
    if not encontrado:
        raise ValueError(f'O arquivo precisa ter o marcador {MARCADOR_TABELA} em algum slide (onde a tabela vai entrar).')
