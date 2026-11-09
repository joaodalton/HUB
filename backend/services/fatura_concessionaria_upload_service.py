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
from models.pendencia import Pendencia
from services.invoice_document_service import has_active_boleto, has_pending_emission, load_invoice_pdf
from services.invoice_parsers.schemas import IssueSeverity
from services.object_storage import get_object_storage
from services.fatura_processing_service import FaturaProcessingService, ProcessingStatus
from services.invoice_parsers.extraction import MinimalExtractor
from services.invoice_parsers.registry import default_registry
from services.uc_code import find_document_ucs

ORIGEM_ERRO_PROCESSAMENTO = 'erro_processamento_fatura'


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
            _fail('Não foi possível ler o código da UC no PDF.', 'UC_NOT_READABLE', 422)
    except InvoiceUploadError:
        raise
    except Exception:
        _fail('Não foi possível ler o código da UC no PDF.', 'UC_NOT_READABLE', 422)

    concessionaria = parsed.identificacao_fiscal.get('concessionaria')
    matches = find_document_ucs(empresa_id, code.value, concessionaria.value if concessionaria else None).limit(2).all()
    if not matches:
        _fail(f'UC {code.value} não está cadastrada em nenhum cliente. Cadastre a UC e importe de novo.',
              'UC_NOT_FOUND', 422)
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
        if existing.deleted_at is not None:
            return _restore(existing, file_bytes), False
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

    # Falha de extracao nao invalida o upload ja persistido; process() grava seu proprio status/erro.
    try:
        resultado = FaturaProcessingService().process(invoice.id, document=file_bytes)
        if any(issue.severity == IssueSeverity.CRITICAL for issue in resultado.issues):
            _registrar_pendencia_erro_processamento(invoice, resultado)
    except Exception:
        current_app.logger.error('Falha ao disparar extracao automatica da fatura: %s', invoice.id)
    _auto_calculate(invoice.id)
    return _result(invoice, False), False


def _auto_calculate(invoice_id: int) -> None:
    """Calcula a cobranca logo apos o vinculo; nunca altera o resultado do upload."""
    try:
        invoice = db.session.get(FaturaConcessionaria, invoice_id)
        if invoice is None or invoice.status_validacao != 'valida':
            return
        from services.billing_calculation_service import BillingCalculationService
        BillingCalculationService().execute(invoice_id)
    except Exception:
        db.session.rollback()
        current_app.logger.error('Falha no calculo automatico da fatura: %s', invoice_id)


_EXTRACTION_FIELDS = (
    'parser_name', 'parser_version', 'layout_name', 'layout_version', 'dados_brutos_extraidos',
    'dados_normalizados', 'consumer_unit_id', 'codigo_uc_extraido', 'chave_acesso', 'competencia',
    'concessionaria', 'numero_nota_fiscal', 'serie_nota_fiscal', 'data_emissao',
    'data_leitura_anterior', 'data_leitura_atual', 'data_proxima_leitura', 'data_vencimento',
    'consumo_kwh', 'energia_compensada_kwh', 'injecao_gd1_kwh', 'injecao_gd2_kwh',
    'saldo_creditos_kwh', 'valor_total_concessionaria',
)


def _restore(invoice: FaturaConcessionaria, file_bytes: bytes) -> dict:
    """Reimporta PDF de fatura excluida logicamente: reativa e reprocessa."""
    invoice.deleted_at = None
    if has_active_boleto(invoice) or has_pending_emission(invoice) is not None:
        db.session.commit()
        return _result(invoice, False)
    return _run_reprocess(invoice, file_bytes)


def reprocess_invoice(invoice_id: int, empresa_id: int) -> dict:
    invoice = FaturaConcessionaria.query.filter_by(
        id=invoice_id, empresa_id=empresa_id, deleted_at=None).first()
    if invoice is None:
        raise LookupError('Fatura nao encontrada.')
    reprocessable = (invoice.status_extracao in ('recebida', 'erro', 'layout_nao_reconhecido')
                     or invoice.status_validacao in ('uc_nao_encontrada', 'uc_pertence_outro_cliente',
                                                     'revisao_necessaria'))
    if (not reprocessable or has_active_boleto(invoice)
            or has_pending_emission(invoice) is not None):
        _fail('Esta fatura nao pode ser reprocessada.', 'REPROCESS_NOT_ALLOWED', 409)
    loaded = load_invoice_pdf(invoice_id, empresa_id)
    if loaded is None:
        raise LookupError('Fatura nao encontrada.')
    return _run_reprocess(invoice, loaded[0])


def _run_reprocess(invoice: FaturaConcessionaria, file_bytes: bytes) -> dict:
    """Zera a extracao e reprocessa; calculos/snapshots antigos ficam como historico."""
    for name in _EXTRACTION_FIELDS:
        setattr(invoice, name, None)
    invoice.status_extracao, invoice.status_validacao = 'recebida', 'pendente'
    db.session.commit()
    try:
        resultado = FaturaProcessingService().process(invoice.id, document=file_bytes)
    except Exception:
        # Como no upload: nao expoe PDF; fatura fica em 'recebida' (reprocessavel).
        db.session.rollback()
        current_app.logger.error('Falha ao reprocessar a fatura: %s', invoice.id)
        return _result(invoice, False)
    critical = any(issue.severity == IssueSeverity.CRITICAL for issue in resultado.issues)
    existing = Pendencia.query.filter_by(empresa_id=invoice.empresa_id,
        fatura_concessionaria_id=invoice.id, origem=ORIGEM_ERRO_PROCESSAMENTO).first()
    if critical and existing is None:
        _registrar_pendencia_erro_processamento(invoice, resultado)
    elif critical:
        existing.status, existing.resolved_at = 'aberta', None
        db.session.commit()
    elif existing is not None and resultado.status == ProcessingStatus.PARSED:
        existing.status, existing.resolved_at = 'resolvida', datetime.utcnow()
        db.session.commit()
    _auto_calculate(invoice.id)
    db.session.refresh(invoice)
    return _result(invoice, False)


def _registrar_pendencia_erro_processamento(invoice: FaturaConcessionaria, resultado) -> None:
    """Pendencia de erro (categoria Documentos) quando o parser encontra issue
    CRITICAL. Dedupe automatico via uq_pendencias_fatura_origem
    (empresa_id, fatura_concessionaria_id, origem) -- nao impede o upload."""
    criticas = [issue.message for issue in resultado.issues if issue.severity == IssueSeverity.CRITICAL]
    pendencia = Pendencia(
        empresa_id=invoice.empresa_id, tipo='erro', categoria='Documentos',
        origem=ORIGEM_ERRO_PROCESSAMENTO,
        titulo=f'Falha ao processar fatura {invoice.id}',
        descricao='Erro(s) critico(s) na extracao: ' + '; '.join(criticas),
        client_id=invoice.client_id, consumer_unit_id=invoice.consumer_unit_id,
        fatura_concessionaria_id=invoice.id, prioridade='alta',
        metadados={'origem': ORIGEM_ERRO_PROCESSAMENTO, 'faturaConcessionariaId': invoice.id},
    )
    try:
        db.session.add(pendencia)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()


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
