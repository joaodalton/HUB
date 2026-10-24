# backend/services/document_service.py
import hashlib
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from flask import current_app, g
from werkzeug.utils import secure_filename

from extensions import db
from models.category import Category
from models.client import Client
from models.consumer_unit import ConsumerUnit
from models.document import Document
from models.fatura_concessionaria import FaturaConcessionaria
from models.plant import Plant
from services.drive_service import get_drive_service
from services.log_service import LogService
from services.object_storage import get_object_storage
from services.settings_service import get_document_storage_provider

# Continua existindo so pra servir documentos antigos (storage_provider='local'),
# enviados antes da troca pro Drive -- nao usar mais pra upload novo (ver
# create_document abaixo). Nao apaga essa pasta nem os arquivos nela.
UPLOAD_ROOT = Path(__file__).resolve().parent.parent / 'uploads'
def _document(identifier): return Document.query.filter_by(id=identifier, empresa_id=g.current_empresa_id).first()
def _client(identifier): return Client.query.filter_by(id=identifier, empresa_id=g.current_empresa_id).first()
def _uc(identifier): return ConsumerUnit.query.filter_by(id=identifier, empresa_id=g.current_empresa_id).first()
def _plant(identifier): return Plant.query.filter_by(id=identifier, empresa_id=g.current_empresa_id).first()

def list_documents(client_id: int | None = None, uc_id: int | None = None, plant_id: int | None = None) -> list[dict]:
    # Documento de boleto/fatura da concessionaria (fatura_concessionaria_upload_service.py)
    # fica salvo no storage, mas nunca deve aparecer na listagem de Documentos do cliente.
    query = Document.query.filter(
        Document.empresa_id == g.current_empresa_id,
        ~Document.id.in_(
            db.session.query(FaturaConcessionaria.document_id)
            .filter(FaturaConcessionaria.empresa_id == g.current_empresa_id)
        ),
    )

    if client_id:
        query = query.filter(Document.client_id == client_id)
    if uc_id:
        query = query.filter(Document.consumer_unit_id == uc_id)
    if plant_id:
        query = query.filter(Document.plant_id == plant_id)

    documents = query.order_by(Document.created_at.desc()).all()
    return [document.to_dict() for document in documents]


def get_document(document_id: int) -> Document | None:
    return _document(document_id)


def prepare_document(data: dict, file_storage) -> tuple[Document, bool]:
    """Upload de documento geral (cliente/UC/usina). Provider resolvido por
    Setting('document_storage_provider') da empresa atual -- 's3' (padrao) ou
    'google_drive' (ver services/settings_service.py:get_document_storage_provider)."""
    category_id = data.get('categoriaId')
    category = db.session.get(Category, category_id) if category_id else None

    if category_id and not category:
        raise ValueError('Categoria informada nao existe.')

    client_id = data.get('clienteId')
    if client_id and not _client(client_id):
        raise ValueError('Cliente informado nao existe.')

    uc_id = data.get('ucId')
    if uc_id and not _uc(uc_id):
        raise ValueError('UC informada nao existe.')

    plant_id = data.get('plantId')
    if plant_id and not _plant(plant_id):
        raise ValueError('Usina informada nao existe.')

    original_name = secure_filename(file_storage.filename or 'arquivo')
    nome = (data.get('nome') or '').strip() or original_name

    if get_document_storage_provider() == 's3':
        return _prepare_s3_document(file_storage, original_name, nome, category, client_id, uc_id, plant_id)
    return _prepare_drive_document(file_storage, original_name, nome, category, client_id, uc_id, plant_id)


def _prepare_drive_document(file_storage, original_name, nome, category, client_id, uc_id, plant_id):
    """Vai pro Google Drive, nao mais pro disco local (ver UPLOAD_ROOT acima:
    so serve pra ler documento antigo, nunca mais escreve nele). Antes de
    enviar, procura no Drive um arquivo com o MESMO nome e o MESMO conteudo
    (md5) -- se achar, reaproveita em vez de subir uma copia nova
    (find_duplicate em drive_service.py)."""
    subfolder = str(client_id) if client_id else 'sem-cliente'
    # Prefixo pelo cliente/uc no nome do arquivo no Drive -- evita que "contrato.pdf"
    # de dois clientes diferentes colidam na checagem de duplicata por nome.
    drive_name = f'{subfolder}_{original_name}'

    file_bytes = file_storage.read()
    file_md5 = hashlib.md5(file_bytes).hexdigest()

    drive = get_drive_service()  # deixa a excecao propagar -- document_routes.py trata como 503, nao 409

    existing_file_id = drive.find_duplicate(drive_name, file_md5, drive.root_folder_id)

    if existing_file_id:
        drive_file_id = existing_file_id
        LogService.info(
            acao='create',
            mensagem=f'Documento "{drive_name}" ja existia identico no Drive -- reaproveitado, sem enviar copia nova',
            entidade='Document',
            metadados={'driveFileId': drive_file_id}
        )
    else:
        drive_file_id = drive.upload_file(file_bytes, drive_name, file_storage.mimetype, drive.root_folder_id)

    document = Document(
        empresa_id=g.current_empresa_id,
        nome=nome,
        client_id=client_id,
        consumer_unit_id=uc_id,
        plant_id=plant_id,
        category_id=category.id if category else None,
        storage_provider='google_drive',
        storage_ref=drive_file_id,
        mime_type=file_storage.mimetype
    )
    db.session.add(document)
    return document, existing_file_id is None


def _s3_context(client_id, uc_id, plant_id) -> str:
    if client_id:
        return f'cliente-{client_id}'
    if uc_id:
        return f'uc-{uc_id}'
    if plant_id:
        return f'usina-{plant_id}'
    return 'geral'


def _lock_dedup_candidate_rows(empresa_id: int, client_id, file_hash: str) -> None:
    """UPDATE (nao SELECT) nas MESMAS linhas que o dedup do upload vai ler,
    ANTES de ler -- trava a linha em producao (Postgres bloqueia UPDATE/DELETE
    concorrente na mesma linha) e serializa via lock de escrita do arquivo
    inteiro em SQLite. Fecha o TOCTOU com _lock_storage_ref_rows() (abaixo):
    se a linha reaproveitada aqui estiver sendo apagada concorrentemente por
    delete_document(), esperamos o commit dela e enxergamos que ja nao existe
    (cai no upload de copia nova) em vez de reaproveitar uma referencia que o
    delete concorrente ja decidiu apagar do bucket."""
    Document.query.filter_by(
        empresa_id=empresa_id, client_id=client_id,
        storage_provider='s3', file_hash=file_hash,
    ).update({'updated_at': datetime.utcnow()}, synchronize_session=False)


def _lock_storage_ref_rows(storage_ref: str, empresa_id: int) -> None:
    """Mesma trava de _lock_dedup_candidate_rows(), do lado do delete: UPDATE
    nas linhas com esse storage_ref ANTES do SELECT que decide se ainda ha
    algum Document usando o objeto."""
    Document.query.filter(
        Document.storage_ref == storage_ref, Document.empresa_id == empresa_id,
    ).update({'updated_at': datetime.utcnow()}, synchronize_session=False)


def _prepare_s3_document(file_storage, original_name, nome, category, client_id, uc_id, plant_id):
    """Sobe pro object storage (R2/S3). Deduplica por hash + empresa + cliente
    antes de subir: se achar Document existente com o mesmo arquivo nesse
    escopo, reaproveita a referencia (storage_ref) em vez de subir copia nova."""
    max_bytes = current_app.config['DOCUMENT_MAX_BYTES']
    file_bytes = file_storage.read(max_bytes + 1)
    if len(file_bytes) > max_bytes:
        raise ValueError('Arquivo excede o tamanho maximo permitido.')
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    _lock_dedup_candidate_rows(g.current_empresa_id, client_id, file_hash)

    duplicate = Document.query.filter_by(
        empresa_id=g.current_empresa_id, client_id=client_id,
        storage_provider='s3', file_hash=file_hash,
    ).first()

    if duplicate:
        storage_ref = duplicate.storage_ref
        uploaded_new = False
        LogService.info(
            acao='create',
            mensagem=f'Documento "{nome}" ja existia identico no storage -- reaproveitado, sem enviar copia nova',
            entidade='Document',
            metadados={'storageRef': storage_ref}
        )
    else:
        ext = Path(original_name).suffix.lower()
        contexto = _s3_context(client_id, uc_id, plant_id)
        storage_ref = f'tenants/{g.current_empresa_id}/documents/{contexto}/{uuid4().hex}{ext}'
        get_object_storage('s3').put(storage_ref, file_bytes, file_storage.mimetype)
        uploaded_new = True

    document = Document(
        empresa_id=g.current_empresa_id,
        nome=nome,
        client_id=client_id,
        consumer_unit_id=uc_id,
        plant_id=plant_id,
        category_id=category.id if category else None,
        storage_provider='s3',
        storage_ref=storage_ref,
        mime_type=file_storage.mimetype,
        file_hash=file_hash,
    )
    db.session.add(document)
    return document, uploaded_new


def discard_prepared_document(document: Document, uploaded_new: bool) -> None:
    """Compensa somente o arquivo remoto criado pela transacao atual."""
    if not uploaded_new or not document.storage_ref:
        return
    if document.storage_provider == 'google_drive':
        get_drive_service().delete_file(document.storage_ref)
    elif document.storage_provider == 's3':
        get_object_storage('s3').delete(document.storage_ref)


def create_document(data: dict, file_storage) -> dict:
    document, uploaded_new = prepare_document(data, file_storage)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        discard_prepared_document(document, uploaded_new)
        raise

    LogService.info(acao='create', mensagem=f'Documento "{document.nome}" enviado', entidade='Document', metadados={'id': document.id})
    return document.to_dict()


def rename_document(document_id: int, novo_nome: str) -> dict | None:
    document = _document(document_id)

    if not document:
        return None

    document.nome = novo_nome.strip()
    db.session.commit()

    LogService.info(acao='rename', mensagem=f'Documento renomeado para "{document.nome}"', entidade='Document', metadados={'id': document.id})
    return document.to_dict()


def delete_document(document_id: int) -> bool:
    document = _document(document_id)

    if not document:
        return False

    if document.storage_provider == 'local' and document.storage_ref:
        file_path = UPLOAD_ROOT / document.storage_ref
        if file_path.exists():
            file_path.unlink()
    elif document.storage_provider == 's3' and document.storage_ref:
        _lock_storage_ref_rows(document.storage_ref, document.empresa_id)

        # Bucket e do HUB (diferente do Drive, que nunca e apagado por nao ser
        # propriedade do HUB) -- seguro apagar o objeto junto com o registro,
        # desde que nenhum outro Document (dedup) ainda aponte pro mesmo objeto.
        shared = Document.query.filter(
            Document.storage_ref == document.storage_ref, Document.id != document.id,
        ).first()
        if not shared:
            get_object_storage('s3').delete(document.storage_ref)

    db.session.delete(document)
    db.session.commit()

    LogService.info(acao='delete', mensagem=f'Documento {document_id} excluido', entidade='Document')
    return True


def resolve_file_path(document: Document) -> Path | None:
    if document.storage_provider != 'local' or not document.storage_ref:
        return None

    root = UPLOAD_ROOT.resolve()
    file_path = (root / document.storage_ref).resolve()
    if not file_path.is_relative_to(root):
        return None
    return file_path if file_path.exists() else None


def load_s3_document(document: Document) -> tuple[bytes, str]:
    """Le um Document 's3' pra download autenticado via backend (sem presigned
    URL). Valida que a chave pertence ao tenant atual antes de ler."""
    reference = document.storage_ref or ''
    if not reference.startswith(f'tenants/{document.empresa_id}/documents/'):
        raise ValueError('Referencia de objeto invalida.')
    max_bytes = current_app.config['DOCUMENT_MAX_BYTES']
    data = get_object_storage('s3').read(reference, max_bytes)
    filename = secure_filename(document.nome) or f'documento-{document.id}'
    return data, filename


def create_drive_document(data: dict) -> dict:
    """Vincula um arquivo que ja esta no Google Drive a um cliente/UC, sem copiar
    nem mover nada -- so cria o registro em Document apontando pro fileId
    (storageProvider='google_drive', storageRef=fileId). O Drive continua sendo
    o armazenamento; o Document e so o catalogo (dono, categoria, UC)."""
    category = db.session.get(Category, data.get('categoriaId'))
    if not category:
        raise ValueError('Categoria informada nao existe.')

    client_id = data.get('clienteId')
    if client_id and not _client(client_id):
        raise ValueError('Cliente informado nao existe.')

    uc_id = data.get('ucId')
    if uc_id and not _uc(uc_id):
        raise ValueError('UC informada nao existe.')

    drive_file_id = (data.get('driveFileId') or '').strip()
    if not drive_file_id:
        raise ValueError('Arquivo do Google Drive nao informado.')

    drive_item = get_drive_service().get_authorized_item(drive_file_id)
    if drive_item.get('mimeType') == 'application/vnd.google-apps.folder':
        raise ValueError('Pastas nao podem ser vinculadas como documento.')

    document = Document(
        empresa_id=g.current_empresa_id,
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
