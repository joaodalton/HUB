import hashlib
from io import BytesIO
from pathlib import Path

from flask import current_app, g
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from sqlalchemy.exc import IntegrityError

from extensions import db
from models.client import Client
from models.fatura_concessionaria import FaturaConcessionaria
from services.document_service import discard_prepared_document, prepare_document


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


def upload_invoice(client_id: int, file_storage) -> tuple[dict, bool]:
    empresa_id = g.current_empresa_id
    client = Client.query.filter_by(id=client_id, empresa_id=empresa_id).first()
    if not client:
        _fail('Cliente nao encontrado.', 'CLIENT_NOT_FOUND', 404)

    file_bytes = _validate_pdf(file_storage)
    arquivo_hash = hashlib.sha256(file_bytes).hexdigest()
    existing = _find_existing(empresa_id, arquivo_hash)
    if existing:
        return _result(existing, True), True

    document = None
    uploaded_new = False
    try:
        document, uploaded_new = prepare_document({
            'clienteId': client.id,
        }, file_storage)
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
        if document is not None and (
            not existing or existing.document.storage_ref != document.storage_ref
        ):
            discard_prepared_document(document, uploaded_new)
        if existing:
            return _result(existing, True), True
        raise
    except Exception:
        db.session.rollback()
        if document is not None:
            discard_prepared_document(document, uploaded_new)
        raise

    return _result(invoice, False), False


def _result(invoice: FaturaConcessionaria, duplicate: bool) -> dict:
    return {
        'duplicate': duplicate,
        'invoiceId': invoice.id,
        'invoice': invoice.to_dict(),
    }
