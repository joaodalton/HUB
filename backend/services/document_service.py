# backend/services/document_service.py
import hashlib
from pathlib import Path

from werkzeug.utils import secure_filename

from extensions import db
from models.category import Category
from models.client import Client
from models.consumer_unit import ConsumerUnit
from models.document import Document
from services.drive_service import get_drive_service
from services.log_service import LogService
from config import Config

# Continua existindo so pra servir documentos antigos (storage_provider='local'),
# enviados antes da troca pro Drive -- nao usar mais pra upload novo (ver
# create_document abaixo). Nao apaga essa pasta nem os arquivos nela.
UPLOAD_ROOT = Path(__file__).resolve().parent.parent / 'uploads'

def list_documents(client_id: int | None = None, uc_id: int | None = None) -> list[dict]:
    query = Document.query

    if client_id:
        query = query.filter(Document.client_id == client_id)
    if uc_id:
        query = query.filter(Document.consumer_unit_id == uc_id)

    documents = query.order_by(Document.created_at.desc()).all()
    return [document.to_dict() for document in documents]


def get_document(document_id: int) -> Document | None:
    return Document.query.get(document_id)


def create_document(data: dict, file_storage) -> dict:
    """Upload de verdade -- vai pro Google Drive, nao mais pro disco local (ver
    UPLOAD_ROOT acima: so serve pra ler documento antigo, nunca mais escreve
    nele). Antes de enviar, procura no Drive um arquivo com o MESMO nome e o
    MESMO conteudo (md5) -- se achar, reaproveita em vez de subir uma copia
    nova (find_duplicate em drive_service.py)."""
    category_id = data.get('categoriaId')
    category = Category.query.get(category_id) if category_id else None

    if category_id and not category:
        raise ValueError('Categoria informada nao existe.')

    client_id = data.get('clienteId')
    if client_id and not Client.query.get(client_id):
        raise ValueError('Cliente informado nao existe.')

    uc_id = data.get('ucId')
    if uc_id and not ConsumerUnit.query.get(uc_id):
        raise ValueError('UC informada nao existe.')

    original_name = secure_filename(file_storage.filename or 'arquivo')
    subfolder = str(client_id) if client_id else 'sem-cliente'
    # Prefixo pelo cliente/uc no nome do arquivo no Drive -- evita que "contrato.pdf"
    # de dois clientes diferentes colidam na checagem de duplicata por nome.
    drive_name = f'{subfolder}_{original_name}'

    file_bytes = file_storage.read()
    file_md5 = hashlib.md5(file_bytes).hexdigest()

    drive = get_drive_service()  # deixa a excecao propagar -- document_routes.py trata como 503, nao 409

    existing_file_id = drive.find_duplicate(drive_name, file_md5, Config.GOOGLE_DRIVE_ROOT_FOLDER_ID)

    if existing_file_id:
        drive_file_id = existing_file_id
        LogService.info(
            acao='create',
            mensagem=f'Documento "{drive_name}" ja existia identico no Drive -- reaproveitado, sem enviar copia nova',
            entidade='Document',
            metadados={'driveFileId': drive_file_id}
        )
    else:
        drive_file_id = drive.upload_file(file_bytes, drive_name, file_storage.mimetype, Config.GOOGLE_DRIVE_ROOT_FOLDER_ID)

    document = Document(
        nome=(data.get('nome') or '').strip() or original_name,
        client_id=client_id,
        consumer_unit_id=uc_id,
        category_id=category.id if category else None,
        storage_provider='google_drive',
        storage_ref=drive_file_id,
        mime_type=file_storage.mimetype
    )
    db.session.add(document)
    db.session.commit()

    LogService.info(acao='create', mensagem=f'Documento "{document.nome}" enviado', entidade='Document', metadados={'id': document.id})
    return document.to_dict()


def rename_document(document_id: int, novo_nome: str) -> dict | None:
    document = Document.query.get(document_id)

    if not document:
        return None

    document.nome = novo_nome.strip()
    db.session.commit()

    LogService.info(acao='rename', mensagem=f'Documento renomeado para "{document.nome}"', entidade='Document', metadados={'id': document.id})
    return document.to_dict()


def delete_document(document_id: int) -> bool:
    document = Document.query.get(document_id)

    if not document:
        return False

    if document.storage_provider == 'local' and document.storage_ref:
        file_path = UPLOAD_ROOT / document.storage_ref
        if file_path.exists():
            file_path.unlink()

    db.session.delete(document)
    db.session.commit()

    LogService.info(acao='delete', mensagem=f'Documento {document_id} excluido', entidade='Document')
    return True


def resolve_file_path(document: Document) -> Path | None:
    if document.storage_provider != 'local' or not document.storage_ref:
        return None

    file_path = UPLOAD_ROOT / document.storage_ref
    return file_path if file_path.exists() else None


def create_drive_document(data: dict) -> dict:
    """Vincula um arquivo que ja esta no Google Drive a um cliente/UC, sem copiar
    nem mover nada -- so cria o registro em Document apontando pro fileId
    (storageProvider='google_drive', storageRef=fileId). O Drive continua sendo
    o armazenamento; o Document e so o catalogo (dono, categoria, UC)."""
    category = Category.query.get(data.get('categoriaId'))
    if not category:
        raise ValueError('Categoria informada nao existe.')

    client_id = data.get('clienteId')
    if client_id and not Client.query.get(client_id):
        raise ValueError('Cliente informado nao existe.')

    uc_id = data.get('ucId')
    if uc_id and not ConsumerUnit.query.get(uc_id):
        raise ValueError('UC informada nao existe.')

    drive_file_id = (data.get('driveFileId') or '').strip()
    if not drive_file_id:
        raise ValueError('Arquivo do Google Drive nao informado.')

    document = Document(
        nome=(data.get('nome') or '').strip() or 'Documento do Drive',
        client_id=client_id,
        consumer_unit_id=uc_id,
        category_id=category.id,
        storage_provider='google_drive',
        storage_ref=drive_file_id,
        mime_type=data.get('mimeType')
    )
    db.session.add(document)
    db.session.commit()

    LogService.info(
        acao='create',
        mensagem=f'Documento "{document.nome}" vinculado do Google Drive',
        entidade='Document',
        metadados={'id': document.id, 'driveFileId': drive_file_id}
    )
    return document.to_dict()