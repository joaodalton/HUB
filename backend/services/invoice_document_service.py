"""Authorized invoice document lookup and provider-aware reading."""
import hashlib

from flask import current_app
from werkzeug.utils import secure_filename

from extensions import db
from models.calculo_cobranca import BillingCalculationExecution
from models.client import Client
from models.document import Document
from models.fatura_concessionaria import FaturaConcessionaria
from models.pendencia import Pendencia
from services.document_service import delete_document, resolve_file_path
from services.object_storage import ObjectStorageError, get_object_storage


class InvoiceHasCalculationError(Exception):
    """Fatura já teve cálculo de cobrança executado; não pode ser excluída."""


def load_invoice_pdf(invoice_id: int, empresa_id: int) -> tuple[bytes, str] | None:
    invoice = FaturaConcessionaria.query.filter_by(id=invoice_id, empresa_id=empresa_id).first()
    if invoice is None:
        return None
    document = Document.query.filter_by(id=invoice.document_id, empresa_id=empresa_id).first()
    if document is None or document.client_id != invoice.client_id or not document.storage_ref:
        return None
    reference = document.storage_ref
    try:
        if document.storage_provider == 's3':
            if not reference.startswith(f'tenants/{empresa_id}/invoices/'):
                raise ObjectStorageError('Referencia de objeto invalida.')
            data = get_object_storage('s3').read(reference,
                current_app.config['FATURA_CONCESSIONARIA_MAX_BYTES'])
        elif document.storage_provider == 'local':
            if reference.startswith(f'tenants/{empresa_id}/invoices/'):
                data = get_object_storage('local').read(reference,
                    current_app.config['FATURA_CONCESSIONARIA_MAX_BYTES'])
            else:
                path = resolve_file_path(document)
                if path is None:
                    raise ObjectStorageError('Arquivo legado indisponivel.')
                data = path.read_bytes()
        elif document.storage_provider == 'google_drive':
            data = get_object_storage('google_drive').read(reference,
                current_app.config['FATURA_CONCESSIONARIA_MAX_BYTES'])
        else:
            raise ObjectStorageError('Provider de documento desconhecido.')
    except Exception as exc:
        raise ObjectStorageError('Documento de fatura indisponivel.') from exc
    if hashlib.sha256(data).hexdigest() != invoice.arquivo_hash:
        raise ObjectStorageError('Integridade do documento de fatura invalida.')
    client = Client.query.filter_by(id=invoice.client_id, empresa_id=empresa_id).first()
    return data, _download_name(invoice, client)


def delete_invoice(invoice_id: int, empresa_id: int) -> bool:
    invoice = FaturaConcessionaria.query.filter_by(id=invoice_id, empresa_id=empresa_id).first()
    if invoice is None:
        return False
    has_calculation = BillingCalculationExecution.query.filter_by(
        fatura_concessionaria_id=invoice_id, empresa_id=empresa_id,
    ).first() is not None
    if has_calculation:
        raise InvoiceHasCalculationError()
    Pendencia.query.filter_by(fatura_concessionaria_id=invoice_id, empresa_id=empresa_id).delete()
    document_id = invoice.document_id
    db.session.delete(invoice)
    db.session.flush()
    delete_document(document_id)
    return True


def _download_name(invoice: FaturaConcessionaria, client: Client | None) -> str:
    client_name = secure_filename(client.nome if client else '')[:100] or f'Fatura_{invoice.id}'
    competence = secure_filename(invoice.competencia or '') or 'sem_competencia'
    due = invoice.data_vencimento.isoformat() if invoice.data_vencimento else 'sem_data'
    return f'{client_name}_{competence}_Vencimento_{due}.pdf'
