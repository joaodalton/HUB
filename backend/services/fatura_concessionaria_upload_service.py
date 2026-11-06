import hashlib
from datetime import datetime
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from flask import current_app, g
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename

from extensions import db
from models.client import Client
from models.consumer_unit import ConsumerUnit
from models.fatura_concessionaria import FaturaConcessionaria
from models.document import Document
from services.object_storage import get_object_storage
from services.invoice_parsers.extraction import MinimalExtractor
from services.invoice_parsers.registry import default_registry
from services.uc_code import find_document_ucs


class InvoiceUploadError(ValueError):
    def __init__(self, message: str, code: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def _fail(message: str, code: str, status_code: int = 400) -> None:
    raise InvoiceUploadError(message, code, status_code)


def _validate_pdf(file_storage) -> bytes:
    filename = file_storage.filename or ''
    if Path(filename).suffix.lower() != '.pdf':
        _fail('Somente arquivos PDF sao permitidos.', 'INVALID_FILE_TYPE')
    if file_storage.mimetype != 'application/pdf':
        _fail('O MIME do arquivo deve ser application/pdf.', 'INVALID_FILE_TYPE')

    max_bytes = current_app.config['FATURA_CONCESSIONARIA_MAX_BYTES']
    max_pages = current_app.config['FATURA_CONCESSIONARIA_MAX_PAGES']
    file_bytes = file_storage.read(max_bytes + 1)
    file_storage.seek(0)

    if not file_bytes:
        _fail('O arquivo PDF esta vazio.', 'INVALID_PDF')
    if len(file_bytes) > max_bytes:
        _fail('O arquivo PDF excede o tamanho maximo permitido.', 'FILE_TOO_LARGE', 413)
    if not file_bytes.startswith(b'%PDF'):
        _fail('O arquivo enviado nao e um PDF valido.', 'INVALID_PDF')

    try:
        reader = PdfReader(BytesIO(file_bytes), strict=True)
        if reader.is_encrypted:
            _fail('PDFs criptografados ou protegidos nao sao aceitos.', 'PDF_ENCRYPTED')
        page_count = len(reader.pages)
    except InvoiceUploadError:
        raise
    except (PdfReadError, ValueError, TypeError, KeyError):
        _fail('O arquivo PDF esta corrompido ou invalido.', 'INVALID_PDF')

    if page_count > max_pages:
        _fail('O PDF excede o limite de paginas.', 'PDF_TOO_MANY_PAGES')
    return file_bytes


def _find_existing(empresa_id: int, arquivo_hash: str) -> FaturaConcessionaria | None:
    return FaturaConcessionaria.query.filter_by(
        empresa_id=empresa_id, arquivo_hash=arquivo_hash,
    ).order_by(FaturaConcessionaria.created_at, FaturaConcessionaria.id).first()


def _client_from_document(file_bytes: bytes, empresa_id: int) -> Client:
    try:
        selection = default_registry().select(MinimalExtractor().extract(file_bytes))
        if selection.parser is None:
            _fail('Layout da fatura nao reconhecido para vinculo automatico.', 'INVOICE_LAYOUT_UNSUPPORTED', 422)
        parsed = selection.parser.parse(file_bytes)
        code = parsed.identificacao_fiscal.get('codigo_uc')
        if code is None or code.status != 'found' or not isinstance(code.value, str):
            _fail('UC da fatura ausente ou ilegivel.', 'UC_CODE_UNREADABLE', 422)
    except InvoiceUploadError:
        raise
    except Exception:
        _fail('Nao foi possivel extrair a UC da fatura.', 'UC_CODE_UNREADABLE', 422)

    concessionaria = parsed.identificacao_fiscal.get('concessionaria')
    matches = find_document_ucs(empresa_id, code.value, concessionaria.value if concessionaria else None).limit(2).all()
    if not matches:
        _fail('UC da fatura nao encontrada nesta empresa.', 'UC_NOT_FOUND', 422)
    if len(matches) != 1:
        _fail('Mais de uma UC corresponde a fatura.', 'UC_MATCH_AMBIGUOUS', 409)
    client = Client.query.filter_by(id=matches[0].client_id, empresa_id=empresa_id).first()
    if client is None:
        _fail('Cliente da UC nao encontrado nesta empresa.', 'CLIENT_NOT_FOUND', 404)
    return client


def upload_invoice(client_id: int | None, file_storage) -> tuple[dict, bool]:
    empresa_id = g.current_empresa_id
    client = Client.query.filter_by(id=client_id, empresa_id=empresa_id).first() if client_id is not None else None
    if client_id is not None and not client:
        _fail('Cliente nao encontrado.', 'CLIENT_NOT_FOUND', 404)

    file_bytes = _validate_pdf(file_storage)
    arquivo_hash = hashlib.sha256(file_bytes).hexdigest()
    if client_id is None:
        client = _client_from_document(file_bytes, empresa_id)
    existing = _find_existing(empresa_id, arquivo_hash)
    if existing:
        if client_id is None and existing.client_id != client.id:
            _fail('Fatura ja recebida com cliente diferente da UC documental.', 'INVOICE_CLIENT_CONFLICT', 409)
        return _result(existing, True), True

    document = None
    storage = None
    storage_key = None
    try:
        now = datetime.utcnow()
        storage_key = (f'tenants/{empresa_id}/invoices/{now.year:04d}/{now.month:02d}/'
                       f'{uuid4().hex}.pdf')
        storage = get_object_storage()
        storage.put(storage_key, file_bytes, 'application/pdf')
        document = Document(
            empresa_id=empresa_id, client_id=client.id,
            nome=secure_filename(file_storage.filename or 'fatura.pdf') or 'fatura.pdf',
            storage_provider=storage.provider, storage_ref=storage_key,
            mime_type='application/pdf',
        )
        db.session.add(document)
        invoice = FaturaConcessionaria(
            empresa_id=empresa_id,
            client_id=client.id,
            consumer_unit_id=None,
            document=document,
            arquivo_hash=arquivo_hash,
        )
        db.session.add(invoice)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        existing = _find_existing(empresa_id, arquivo_hash)
        if storage is not None and storage_key is not None:
            _discard_attempt(storage, storage_key)
        if existing:
            if client_id is None and existing.client_id != client.id:
                _fail('Fatura ja recebida com cliente diferente da UC documental.', 'INVOICE_CLIENT_CONFLICT', 409)
            return _result(existing, True), True
        raise
    except Exception:
        db.session.rollback()
        if storage is not None and storage_key is not None:
            _discard_attempt(storage, storage_key)
        raise

    return _result(invoice, False), False


def _discard_attempt(storage, key: str) -> None:
    """Only the unique object key generated by this upload may be compensated."""
    try:
        storage.delete(key)
    except Exception:
        # The opaque key allows operational reconciliation without logging PDF data.
        current_app.logger.error('Falha ao compensar objeto de fatura: %s', key)


def _result(invoice: FaturaConcessionaria, duplicate: bool) -> dict:
    return {
        'duplicate': duplicate,
        'invoiceId': invoice.id,
        'invoice': invoice.to_dict(),
    }
