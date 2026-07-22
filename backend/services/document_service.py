# backend/services/document_service.py
import uuid
from pathlib import Path

from werkzeug.utils import secure_filename

from extensions import db
from models.category import Category
from models.client import Client
from models.consumer_unit import ConsumerUnit
from models.document import Document
from services.log_service import LogService

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
    category = Category.query.get(data.get('categoriaId'))
    if not category:
        raise ValueError('Categoria informada nao existe.')

    client_id = data.get('clienteId')
    if client_id and not Client.query.get(client_id):
        raise ValueError('Cliente informado nao existe.')

    uc_id = data.get('ucId')
    if uc_id and not ConsumerUnit.query.get(uc_id):
        raise ValueError('UC informada nao existe.')

    original_name = secure_filename(file_storage.filename or 'arquivo')
    stored_name = f'{uuid.uuid4().hex}_{original_name}'
    subfolder = str(client_id) if client_id else 'sem-cliente'

    destination_folder = UPLOAD_ROOT / subfolder
    destination_folder.mkdir(parents=True, exist_ok=True)
    file_storage.save(destination_folder / stored_name)

    document = Document(
        nome=(data.get('nome') or '').strip() or original_name,
        client_id=client_id,
        consumer_unit_id=uc_id,
        category_id=category.id,
        storage_provider='local',
        storage_ref=f'{subfolder}/{stored_name}',
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