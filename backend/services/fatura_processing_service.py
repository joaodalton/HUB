"""Pipeline documental transacional; sem download ou regras financeiras."""
import hashlib
from dataclasses import dataclass, replace
from enum import Enum

from flask import g
from sqlalchemy import String, cast, or_, update

from extensions import db
from models.client import Client
from models.consumer_unit import ConsumerUnit
from models.document import Document
from models.empresa import Empresa
from models.fatura_concessionaria import FaturaConcessionaria
from services.invoice_normalization_service import InvoiceNormalized, InvoiceNormalizer, json_safe
from services.invoice_validation_service import InvoiceValidationResult, InvoiceValidator, UCMatchCandidate
from services.invoice_parsers.extraction import MinimalExtractor
from services.invoice_parsers.registry import ParserRegistry, default_registry
from services.invoice_parsers.schemas import (
    ExtractedField, ExtractionIssue, IssueSeverity, ParsedInvoice, RawExtraction,
)


class ProcessingStatus(str, Enum):
    PARSED = 'parsed'  # indica pipeline completo, não necessariamente validação aprovada
    NOT_RECOGNIZED = 'layout_nao_reconhecido'
    AMBIGUOUS = 'ambiguous'
    ERROR = 'erro'


@dataclass(frozen=True)
class ProcessingResult:
    status: ProcessingStatus
    raw: RawExtraction | None = None
    parsed: ParsedInvoice | None = None
    issues: tuple[ExtractionIssue, ...] = ()
    normalized: InvoiceNormalized | None = None
    validation: InvoiceValidationResult | None = None


class FaturaProcessingService:
    def __init__(self, registry: ParserRegistry | None = None):
        self.registry = registry if registry is not None else default_registry()

    def process(self, fatura_id: int, *, document: bytes, persist: bool = True) -> ProcessingResult:
        """Contexto tenant obrigatório; chamador fornece o PDF original validado.

        Worker futuro deve estabelecer o contexto autenticado antes de chamar.
        Dono da transação quando persist=True; chamador deve usar sessão limpa.
        persist=False mantém diagnóstico em memória, sem gravar/commitar.
        """
        empresa_id = getattr(g, 'current_empresa_id', None)
        if empresa_id is None:
            return self._error('TENANT_REQUIRED', 'Contexto de empresa obrigatório.')
        if persist and (db.session.new or db.session.dirty or db.session.deleted):
            return self._error('CLEAN_SESSION_REQUIRED', 'Processamento exige sessão sem alterações pendentes.')
        invoice = FaturaConcessionaria.query.filter_by(
            id=fatura_id, empresa_id=empresa_id,
        ).first()
        if invoice is None:
            return self._error('INVOICE_NOT_FOUND', 'Fatura não encontrada.')
        source = Document.query.filter_by(
            id=invoice.document_id, empresa_id=empresa_id,
        ).first()
        if source is None:
            return self._error('DOCUMENT_NOT_FOUND', 'Documento não encontrado.')
        if not isinstance(document, bytes) or hashlib.sha256(document).hexdigest() != invoice.arquivo_hash:
            return self._error('DOCUMENT_HASH_MISMATCH', 'PDF difere do original armazenado.')
        if Client.query.filter_by(id=invoice.client_id, empresa_id=empresa_id).first() is None:
            return self._error('CLIENT_NOT_FOUND', 'Cliente não encontrado.')
        if persist and (any(getattr(invoice, name) is not None for name in (
                'parser_name', 'parser_version', 'layout_name', 'layout_version',
                'dados_brutos_extraidos', 'dados_normalizados', 'consumer_unit_id',
                'codigo_uc_extraido', 'chave_acesso', 'competencia', 'concessionaria',
                'numero_nota_fiscal', 'serie_nota_fiscal', 'data_emissao',
                'data_leitura_anterior', 'data_leitura_atual', 'data_proxima_leitura',
                'data_vencimento', 'consumo_kwh', 'energia_compensada_kwh',
                'injecao_gd1_kwh', 'injecao_gd2_kwh', 'saldo_creditos_kwh',
                'valor_total_concessionaria'))
                or invoice.status_extracao in ('extraida', 'processando')):
            return self._error('REPROCESSING_BLOCKED', 'Extração existente exige versionamento; sobrescrita bloqueada.')
        original = (invoice.id, empresa_id, invoice.updated_at, invoice.arquivo_hash)

        try:
            raw = MinimalExtractor().extract(document)
            selection = self.registry.select(raw)
            if selection.parser is None:
                status = (
                    ProcessingStatus.AMBIGUOUS
                    if selection.issues[0].code == 'AMBIGUOUS_LAYOUT'
                    else ProcessingStatus.NOT_RECOGNIZED
                )
                if persist:
                    self._save(original, {'status_extracao': 'erro' if status == ProcessingStatus.AMBIGUOUS else status.value,
                                          'status_validacao': 'pendente'})
                return ProcessingResult(status, raw=raw, issues=raw.warnings + selection.issues)
            parsed = selection.parser.parse(document)
            if not isinstance(parsed, ParsedInvoice) or parsed.identity != selection.parser.identity:
                raise ValueError('Contrato/versionamento incompatível com o parser selecionado.')
            normalized = InvoiceNormalizer().normalize(parsed, empresa_id=empresa_id, client_id=invoice.client_id,
                                                       fatura_concessionaria_id=invoice.id)
            if persist:
                # ponytail: serializa processamento por empresa no PostgreSQL;
                # reduzir lock quando houver histórico de extrações dedicado.
                Empresa.query.filter_by(id=empresa_id).with_for_update().one()
            code = normalized.campos['codigo_uc_documental']
            matches = []
            if code.status == 'found':
                query = ConsumerUnit.query.populate_existing().filter(ConsumerUnit.empresa_id == empresa_id, or_(
                    ConsumerUnit.codigo == code.value, ConsumerUnit.codigo_aneel == code.value))
                if persist:
                    query = query.with_for_update()
                matches = [UCMatchCandidate(c.id, c.empresa_id, c.client_id, c.codigo) for c in query.all()]
            key = normalized.campos['chave_acesso']
            conflict = key.status == 'found' and FaturaConcessionaria.query.filter(
                FaturaConcessionaria.empresa_id == empresa_id,
                FaturaConcessionaria.id != invoice.id,
                FaturaConcessionaria.chave_acesso == key.value,
                FaturaConcessionaria.arquivo_hash != invoice.arquivo_hash,
            ).first() is not None
            validation = InvoiceValidator().validate(normalized, candidates=matches, fiscal_conflict=conflict)
            if validation.consumer_unit_id is not None:
                normalized = replace(normalized, consumer_unit_id=validation.consumer_unit_id,
                                     campos={**normalized.campos, 'uc_numero': ExtractedField(
                                         'found', validation.uc_numero, source='matching exato tenant-scoped')})
            if persist:
                values = {
                    'status_extracao': 'extraida', 'status_validacao': validation.status,
                    'consumer_unit_id': validation.consumer_unit_id,
                    **json_safe(parsed.identity),
                    'dados_brutos_extraidos': json_safe(parsed),
                    'dados_normalizados': {'invoice': json_safe(normalized), 'validation': json_safe(validation)},
                }
                mapping = {
                    'concessionaria': 'concessionaria', 'codigo_uc_extraido': 'codigo_uc_documental',
                    'competencia': 'mes_referencia', 'numero_nota_fiscal': 'numero_nota_fiscal',
                    'serie_nota_fiscal': 'serie_nota_fiscal', 'chave_acesso': 'chave_acesso',
                    'data_emissao': 'data_emissao', 'data_leitura_anterior': 'data_leitura_anterior',
                    'data_leitura_atual': 'data_leitura', 'data_proxima_leitura': 'data_proxima_leitura',
                    'data_vencimento': 'data_vencimento',
                }
                for column, name in mapping.items():
                    value = normalized.campos[name]
                    if value.status == 'found':
                        values[column] = value.value
                # Numeric do model tem escala limitada: JSON é a fonte exata.
                self._save(original, values)
            return ProcessingResult(
                ProcessingStatus.PARSED, raw=raw, parsed=parsed,
                issues=raw.warnings + validation.issues, normalized=normalized, validation=validation,
            )
        except Exception:
            if persist:
                db.session.rollback()
            # Não expor conteúdo do PDF, paths ou detalhes da exceção ao consumidor.
            return self._error('PARSING_EXECUTION_FAILED', 'Falha técnica no processamento do PDF.')

    @staticmethod
    def _save(original, values):
        identifier, tenant, updated_at, digest = original
        table = FaturaConcessionaria
        result = db.session.execute(update(table).where(
            table.id == identifier, table.empresa_id == tenant,
            table.updated_at == updated_at, table.arquivo_hash == digest,
            table.parser_name.is_(None),
            # PostgreSQL JSON (não JSONB) não oferece operador de igualdade.
            or_(table.dados_brutos_extraidos.is_(None), cast(table.dados_brutos_extraidos, String) == 'null'),
            or_(table.dados_normalizados.is_(None), cast(table.dados_normalizados, String) == 'null'),
            table.status_extracao.in_(('recebida', 'erro', 'layout_nao_reconhecido')),
        ).values(**values).execution_options(synchronize_session=False))
        if result.rowcount != 1:
            raise RuntimeError('Concorrência ou extração já existente.')
        db.session.commit()
        db.session.expire_all()

    @staticmethod
    def _error(code: str, message: str) -> ProcessingResult:
        return ProcessingResult(ProcessingStatus.ERROR, issues=(
            ExtractionIssue(code, IssueSeverity.CRITICAL, message),
        ))
