"""Authorized invoice document lookup and provider-aware reading."""
import hashlib
from datetime import datetime

from flask import current_app
from werkzeug.utils import secure_filename

from extensions import db
from models.client import Client
from models.document import Document
from models.fatura import Fatura
from models.fatura_concessionaria import FaturaConcessionaria
from models.pendencia import Pendencia
from services.document_service import resolve_file_path
from services.object_storage import ObjectStorageError, get_object_storage


class InvoiceHasBoletoError(Exception):
    """Fatura tem boleto ativo ou emissão pendente; não pode ser excluída."""


def active_boleto(invoice: FaturaConcessionaria) -> Fatura | None:
    if invoice.consumer_unit_id is None or invoice.competencia is None:
        return None
    return Fatura.query.filter(
        Fatura.empresa_id == invoice.empresa_id, Fatura.consumer_unit_id == invoice.consumer_unit_id,
        Fatura.competencia == invoice.competencia, Fatura.asaas_id.isnot(None),
        Fatura.asaas_status.notin_(('canceled', 'refunded')),
    ).first()


def has_active_boleto(invoice: FaturaConcessionaria) -> bool:
    return active_boleto(invoice) is not None


def has_pending_emission(invoice: FaturaConcessionaria) -> Fatura | None:
    if invoice.consumer_unit_id is None or invoice.competencia is None:
        return None
    return Fatura.query.filter(
        Fatura.empresa_id == invoice.empresa_id, Fatura.consumer_unit_id == invoice.consumer_unit_id,
        Fatura.competencia == invoice.competencia, Fatura.asaas_id.is_(None),
        Fatura.status_interno.in_(('aguardando_emissao', 'erro_emissao')),
    ).first()


def load_invoice_pdf(invoice_id: int, empresa_id: int) -> tuple[bytes, str] | None:
    invoice = FaturaConcessionaria.query.filter_by(
        id=invoice_id, empresa_id=empresa_id, deleted_at=None).first()
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
    """Exclusão lógica: cálculos/snapshots são imutáveis e permanecem como histórico."""
    invoice = FaturaConcessionaria.query.filter_by(
        id=invoice_id, empresa_id=empresa_id, deleted_at=None).first()
    if invoice is None:
        return False
    if has_active_boleto(invoice) or has_pending_emission(invoice) is not None:
        raise InvoiceHasBoletoError()
    Pendencia.query.filter_by(fatura_concessionaria_id=invoice_id, empresa_id=empresa_id).delete()
    invoice.deleted_at = datetime.utcnow()
    db.session.commit()
    return True


def _download_name(invoice: FaturaConcessionaria, client: Client | None) -> str:
    client_name = secure_filename(client.nome if client else '')[:100] or f'Fatura_{invoice.id}'
    competence = secure_filename(invoice.competencia or '') or 'sem_competencia'
    due = invoice.data_vencimento.isoformat() if invoice.data_vencimento else 'sem_data'
    return f'{client_name}_{competence}_Vencimento_{due}.pdf'
