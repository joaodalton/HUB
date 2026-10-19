"""Dados escritos no documento; nenhuma interpretação financeira do HUB."""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Generic, TypeVar


class FieldStatus(str, Enum):
    FOUND = 'found'
    NOT_PRESENT = 'not_present'
    FAILED = 'failed'
    AMBIGUOUS = 'ambiguous'


class IssueSeverity(str, Enum):
    INFO = 'info'
    WARNING = 'warning'
    CRITICAL = 'critical'


@dataclass(frozen=True)
class ExtractionIssue:
    code: str
    severity: IssueSeverity
    message: str
    field: str | None = None
    metadata: dict[str, str] | None = None

    def __post_init__(self):
        object.__setattr__(self, 'severity', IssueSeverity(self.severity))
        if not self.code.strip() or not self.message.strip():
            raise ValueError('Issue exige code e message.')


Scalar = str | int | bool | Decimal | date
T = TypeVar('T', bound=Scalar)


@dataclass(frozen=True)
class ExtractedField(Generic[T]):
    status: FieldStatus
    value: T | None = None
    confidence: Decimal | None = None
    source: str | None = None
    warnings: tuple[ExtractionIssue, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, 'status', FieldStatus(self.status))
        if self.status == FieldStatus.FOUND and self.value is None:
            raise ValueError('found exige value.')
        if self.status in (FieldStatus.NOT_PRESENT, FieldStatus.FAILED) and self.value is not None:
            raise ValueError('not_present/failed exigem value ausente.')
        if self.value is not None and not isinstance(self.value, (str, int, Decimal, date)):
            raise TypeError('Valor deve ser escalar; use Decimal em vez de float.')
        if isinstance(self.value, Decimal) and not self.value.is_finite():
            raise ValueError('Decimal deve ser finito.')
        if self.confidence is not None:
            if not isinstance(self.confidence, Decimal):
                raise TypeError('confidence deve ser Decimal.')
            if not self.confidence.is_finite() or not 0 <= self.confidence <= 1:
                raise ValueError('confidence deve estar entre 0 e 1.')


@dataclass(frozen=True)
class ParserIdentity:
    parser_name: str
    parser_version: str
    layout_name: str | None = None
    layout_version: str | None = None

    def __post_init__(self):
        if not self.parser_name.strip() or not self.parser_version.strip():
            raise ValueError('Parser exige nome e versão.')
        if (self.layout_name is None) != (self.layout_version is None):
            raise ValueError('Layout exige nome e versão juntos.')
        if self.layout_name is not None and (
            not self.layout_name.strip() or not self.layout_version.strip()
        ):
            raise ValueError('Nome e versão do layout não podem ser vazios.')


@dataclass(frozen=True)
class RawWord:
    text: str
    page: int  # páginas começam em 1; coordenadas em pontos PDF
    x0: float
    top: float
    x1: float
    bottom: float


@dataclass(frozen=True)
class RawTable:
    page: int
    rows: tuple[tuple[str | None, ...], ...]


@dataclass(frozen=True)
class RawExtraction:
    text: str
    page_count: int
    extracted_pages: tuple[int, ...]
    metadata: dict[str, str] = field(default_factory=dict)
    words: tuple[RawWord, ...] | None = None
    tables: tuple[RawTable, ...] | None = None
    warnings: tuple[ExtractionIssue, ...] = ()
    page_texts: tuple[str, ...] = ()  # texto por página, quando extração completa


# Chaves preservam os rótulos documentais. Ausência de chave = não examinado;
# campo examinado sempre contém ExtractedField, inclusive quando ausente/falho.
FieldMap = dict[str, ExtractedField[Scalar]]


@dataclass(frozen=True)
class ParsedInvoice:
    identity: ParserIdentity
    source_metadata: dict[str, str] = field(default_factory=dict)
    identificacao_fiscal: FieldMap = field(default_factory=dict)
    titular: FieldMap = field(default_factory=dict)
    classificacao: FieldMap = field(default_factory=dict)
    leituras: tuple[FieldMap, ...] = ()
    resumo: FieldMap = field(default_factory=dict)
    itens: tuple[FieldMap, ...] = ()
    tributos: tuple[FieldMap, ...] = ()
    historico_consumo: tuple[FieldMap, ...] = ()
    medidor: FieldMap = field(default_factory=dict)
    boleto_original: FieldMap = field(default_factory=dict)
    avisos: tuple[ExtractedField[str], ...] = ()
    energia: FieldMap = field(default_factory=dict)
    issues: tuple[ExtractionIssue, ...] = ()

    # Componentes individuais; nunca um total agregado. item_index referencia
    # a linha original em itens; demais campos também usam ExtractedField.
    energy_components: tuple[FieldMap, ...] = ()
    compensation_supported: bool = False

    def __post_init__(self):
        if type(self.compensation_supported) is not bool:
            raise TypeError('Suporte a compensação exige declaração explícita do parser.')
        if not isinstance(self.identity, ParserIdentity):
            raise TypeError('ParsedInvoice exige ParserIdentity.')
        sections = (
            self.identificacao_fiscal, self.titular, self.classificacao,
            self.resumo, self.medidor, self.boleto_original, self.energia,
            *self.leituras, *self.itens, *self.tributos, *self.historico_consumo,
            *self.energy_components,
        )
        for section in sections:
            if not isinstance(section, dict) or any(
                not isinstance(key, str) or not isinstance(value, ExtractedField)
                for key, value in section.items()
            ):
                raise TypeError('Seções exigem rótulos e ExtractedField.')
        if any(not isinstance(value, ExtractedField) for value in self.avisos):
            raise TypeError('Avisos exigem ExtractedField.')
