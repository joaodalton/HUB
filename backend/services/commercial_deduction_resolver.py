"""Deducoes documentais vinculadas a eventos; sem rateio ou inferencia tributaria."""
from dataclasses import dataclass
from copy import deepcopy
from decimal import Decimal, localcontext
from enum import Enum
import re

from services.billing_calculation_contracts import BillingCalculationIssue, ResolvedBillingRule
from services.invoice_compensation import CompensacaoNormalizada, EnergyStatus
from services.invoice_normalization_service import InvoiceNormalized, json_safe
from services.invoice_parsers.schemas import ExtractedField
from services.fio_b_resolver import FioBResolver, FioBResolution


class CommercialDeductionKind(str, Enum):
    PIS = 'PIS'
    COFINS = 'COFINS'


def _sum(values):
    values = tuple(values)
    if not values:
        return Decimal(0)
    with localcontext() as context:
        context.prec = max(v.adjusted() for v in values) - min(v.as_tuple().exponent for v in values) + len(str(len(values))) + 2
        return sum(values, Decimal(0))


def _status(statuses):
    statuses = tuple(statuses)
    return next((s for s in (EnergyStatus.AMBIGUOUS, EnergyStatus.UNSUPPORTED,
                            EnergyStatus.MISSING) if s in statuses), EnergyStatus.VALID)


@dataclass(frozen=True)
class DocumentDeductionEvidence:
    """Vinculo comprovado pelo produtor; totais tributarios nao sao este contrato."""
    kind: CommercialDeductionKind
    event: CompensacaoNormalizada
    amount: ExtractedField
    source_item_indexes: tuple[int, ...]
    document_reference: str
    fatura_concessionaria_id: int
    competencia: str
    source: str = 'DOCUMENT'

    def __post_init__(self):
        object.__setattr__(self, 'kind', CommercialDeductionKind(self.kind))
        if self.source != 'DOCUMENT':
            raise ValueError('Dedução tributária exige origem DOCUMENT.')
        if not isinstance(self.event, CompensacaoNormalizada) or not isinstance(self.amount, ExtractedField):
            raise TypeError('Evidencia exige evento e ExtractedField.')
        if type(self.fatura_concessionaria_id) is not int or self.fatura_concessionaria_id <= 0:
            raise ValueError('Evidencia exige identidade positiva da fatura.')
        if not isinstance(self.competencia, str) or not re.fullmatch(r'(?!0000)[0-9]{4}-(0[1-9]|1[0-2])', self.competencia):
            raise ValueError('Competencia deve ser YYYY-MM.')
        if not isinstance(self.document_reference, str) or not self.document_reference.strip():
            raise ValueError('Vinculo documental deve ser explicito.')
        indexes = tuple(self.source_item_indexes)
        if len(indexes) != 1 or type(indexes[0]) is not int or indexes[0] < 0:
            raise ValueError('Evidencia monetaria exige uma linha documental.')
        object.__setattr__(self, 'source_item_indexes', indexes)


@dataclass(frozen=True)
class ResolvedCommercialDeduction:
    kind: CommercialDeductionKind
    amount: Decimal | None
    applies_to_event: CompensacaoNormalizada | None
    status: EnergyStatus
    source_item_indexes: tuple[int, ...] = ()
    confidence: Decimal | None = None
    issues: tuple[BillingCalculationIssue, ...] = ()
    evidence: tuple[DocumentDeductionEvidence, ...] = ()
    document_tax: dict | None = None

    def __post_init__(self):
        object.__setattr__(self, 'kind', CommercialDeductionKind(self.kind))
        object.__setattr__(self, 'status', EnergyStatus(self.status))
        if self.status == EnergyStatus.VALID:
            if not isinstance(self.amount, Decimal) or not self.amount.is_finite() or self.amount < 0:
                raise ValueError('Deducao valida exige Decimal nao negativo.')
            if not self.evidence or self.applies_to_event is None:
                raise ValueError('Deducao valida exige evidencia vinculada.')
        elif self.amount is not None:
            raise ValueError('Deducao bloqueada nao fornece valor.')
        if self.confidence is not None and (not isinstance(self.confidence, Decimal)
                or not self.confidence.is_finite() or not 0 <= self.confidence <= 1):
            raise ValueError('Confianca exige Decimal entre zero e um.')
        for name in ('source_item_indexes', 'issues', 'evidence'):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        if any(not isinstance(i, BillingCalculationIssue) for i in self.issues):
            raise TypeError('Issues exigem BillingCalculationIssue.')
        if any(not isinstance(e, DocumentDeductionEvidence) for e in self.evidence):
            raise TypeError('Evidencias exigem DocumentDeductionEvidence.')
        if self.applies_to_event is not None and not isinstance(self.applies_to_event, CompensacaoNormalizada):
            raise TypeError('Deducao exige evento normalizado.')
        if self.status == EnergyStatus.VALID:
            if (len(self.evidence) != 1 or self.evidence[0].event != self.applies_to_event
                    or self.evidence[0].kind != self.kind
                    or self.evidence[0].amount.status != 'found'
                    or self.evidence[0].amount.value != self.amount
                    or self.evidence[0].source_item_indexes != self.source_item_indexes
                    or self.applies_to_event.status != EnergyStatus.VALID):
                raise ValueError('Deducao valida deve preservar exatamente a evidencia e o evento.')
            if (not _tax_document_matches(self.document_tax, self.kind, self.applies_to_event)
                    or self.document_tax['valor'] != self.evidence[0].amount):
                raise ValueError('Dedução exige quadro fiscal documental vinculado ao evento.')
        json_safe(self.document_tax)
        object.__setattr__(self, 'document_tax', deepcopy(self.document_tax))


@dataclass(frozen=True)
class ResolvedCommercialDeductions:
    deductions: tuple[ResolvedCommercialDeduction, ...] = ()
    issues: tuple[BillingCalculationIssue, ...] = ()
    fio_b_components: tuple[FioBResolution, ...] = ()
    fio_b_enabled: bool = False

    def __post_init__(self):
        object.__setattr__(self, 'deductions', tuple(self.deductions))
        object.__setattr__(self, 'issues', tuple(self.issues))
        object.__setattr__(self, 'fio_b_components', tuple(self.fio_b_components))
        if type(self.fio_b_enabled) is not bool or any(
                not isinstance(item, FioBResolution) for item in self.fio_b_components):
            raise TypeError('Fio B exige componentes resolvidos e habilitação explícita.')
        if any(not isinstance(d, ResolvedCommercialDeduction) for d in self.deductions):
            raise TypeError('Deducoes exigem contratos resolvidos.')
        if any(not isinstance(i, BillingCalculationIssue) for i in self.issues):
            raise TypeError('Issues exigem BillingCalculationIssue.')

    @property
    def status(self):
        statuses = [d.status for d in self.deductions]
        if self.fio_b_enabled:
            statuses.extend({'RESOLVED': EnergyStatus.VALID, 'NOT_APPLICABLE': EnergyStatus.VALID,
                'MISSING_DATA': EnergyStatus.MISSING, 'UNSUPPORTED': EnergyStatus.UNSUPPORTED,
                'AMBIGUOUS': EnergyStatus.AMBIGUOUS}[row.status] for row in self.fio_b_components)
        return _status(statuses)

    def _total(self, *kinds):
        selected = tuple(d for d in self.deductions if d.kind in kinds)
        return None if any(d.status != EnergyStatus.VALID for d in selected) else _sum(d.amount for d in selected)

    @property
    def total_pis(self):
        return self._total(CommercialDeductionKind.PIS)

    @property
    def total_cofins(self):
        return self._total(CommercialDeductionKind.COFINS)

    @property
    def total_pis_cofins(self):
        return self._total(CommercialDeductionKind.PIS, CommercialDeductionKind.COFINS)

    @property
    def total_fio_b(self):
        if not self.fio_b_enabled:
            return Decimal(0)
        if not self.fio_b_components or any(row.status not in ('RESOLVED', 'NOT_APPLICABLE')
                                            for row in self.fio_b_components):
            return None
        return _sum(row.amount for row in self.fio_b_components if row.status == 'RESOLVED')

    def to_dict(self):
        return {**json_safe(self), 'status': self.status.value,
                **{name: json_safe(getattr(self, name)) for name in
                   ('total_pis', 'total_cofins', 'total_pis_cofins', 'total_fio_b')}}


class CommercialDeductionResolver:
    def resolve(self, *, invoice: InvoiceNormalized, rule: ResolvedBillingRule,
                evidence: tuple[DocumentDeductionEvidence, ...] = (), regulatory_tariffs=()):
        if not isinstance(invoice, InvoiceNormalized) or not isinstance(rule, ResolvedBillingRule):
            raise TypeError('Resolver exige InvoiceNormalized e ResolvedBillingRule.')
        evidence = tuple(evidence)
        if any(not isinstance(e, DocumentDeductionEvidence) for e in evidence):
            raise TypeError('Evidencias exigem DocumentDeductionEvidence.')
        enabled = []
        if rule.billing_modifiers.exclude_pis_cofins is True:
            enabled.extend((CommercialDeductionKind.PIS, CommercialDeductionKind.COFINS))
        fio_b = FioBResolver().resolve(invoice, regulatory_tariffs=regulatory_tariffs)
        energy = invoice.billing_energy_input
        events = tuple(e for e in energy.compensacoes if e.cobravel_ouc_mpt) if energy else ()
        deductions = []

        def blocked(kind, event, status, code, candidates=()):
            issue = BillingCalculationIssue(code, 'critical', 'Deducao sem evidencia unica e vinculada a compensacao cobravel.')
            return ResolvedCommercialDeduction(kind, None, event, status,
                tuple(sorted({i for e in candidates for i in e.source_item_indexes})),
                issues=(issue,), evidence=tuple(candidates))

        for kind in enabled:
            eligible = events
            if not eligible:
                deductions.append(blocked(kind, None, EnergyStatus.MISSING, 'DEDUCAO_SEM_EVIDENCIA'))
            for event in eligible:
                candidates = tuple(e for e in evidence if e.kind == kind and e.event == event)
                if event.status != EnergyStatus.VALID or energy.status != EnergyStatus.VALID:
                    deductions.append(blocked(kind, event, _status((event.status, energy.status)), 'DEDUCAO_EVENTO_INVALIDO', candidates))
                    continue
                if len(candidates) != 1:
                    deductions.append(blocked(kind, event, EnergyStatus.AMBIGUOUS if candidates else EnergyStatus.MISSING,
                        f'{kind.value}_AMBIGUO' if candidates else f'{kind.value}_NAO_RESOLVIDO', candidates))
                    continue
                item = candidates[0]
                field = item.amount
                reused = any(other is not item
                             and set(item.source_item_indexes) & set(other.source_item_indexes) for other in evidence)
                if reused or field.status == 'ambiguous':
                    deductions.append(blocked(kind, event, EnergyStatus.AMBIGUOUS, 'DEDUCAO_EVIDENCIA_AMBIGUA', candidates))
                    continue
                valid = (item.fatura_concessionaria_id == energy.fatura_concessionaria_id
                    and item.competencia == energy.competencia
                    and field.status == 'found' and isinstance(field.value, Decimal)
                    and field.value.is_finite() and field.value >= 0
                    and isinstance(field.source, str) and bool(field.source.strip())
                    and all(i < len(invoice.itens_documentais) for i in item.source_item_indexes)
                    and item.document_reference == f'itens_documentais[{item.source_item_indexes[0]}].valor'
                    and all(field == invoice.itens_documentais[i].get('valor')
                            and _tax_document_matches(invoice.itens_documentais[i], kind, event)
                            for i in item.source_item_indexes if i < len(invoice.itens_documentais)))
                if not valid:
                    deductions.append(blocked(kind, event, EnergyStatus.MISSING, 'DEDUCAO_SEM_EVIDENCIA', candidates))
                    continue
                deductions.append(ResolvedCommercialDeduction(kind, field.value, event, EnergyStatus.VALID,
                    item.source_item_indexes, min(field.confidence, event.confidence)
                    if field.confidence is not None and event.confidence is not None else None,
                    evidence=candidates, document_tax=invoice.itens_documentais[item.source_item_indexes[0]]))
        fio_enabled = rule.billing_modifiers.exclude_gdii_fio_b is True
        issues = tuple(i for d in deductions for i in d.issues)
        if fio_enabled:
            issues += tuple(BillingCalculationIssue(f'FIO_B_{row.status}', 'critical',
                'Fio B sem enquadramento, regra ou tarifa comprovada.') for row in fio_b
                if row.status not in ('RESOLVED', 'NOT_APPLICABLE'))
        return ResolvedCommercialDeductions(tuple(deductions), issues, fio_b, fio_enabled)


def _tax_document_matches(row, kind, event):
    if not isinstance(row, dict):
        return False
    expected = {'tributo': kind.value, 'origin': 'OUC', 'period': 'MPT',
                'gd_classification': event.classificacao_gd,
                'compensation_context': event.contexto_documental}
    if event.mes_origem is not None:
        expected['credit_month'] = event.mes_origem
    else:
        month = row.get('credit_month')
        if month is not None and (not isinstance(month, ExtractedField) or month.status != 'not_present'):
            return False
    for name, value in expected.items():
        field = row.get(name)
        if (not isinstance(field, ExtractedField) or field.status != 'found'
                or not isinstance(field.source, str) or not field.source.strip()):
            return False
        if field.value != value and not (name == 'tributo' and value == 'PIS' and field.value == 'PIS/PASEP'):
            return False
    for name in ('base_calculo', 'aliquota', 'valor'):
        field = row.get(name)
        if (not isinstance(field, ExtractedField) or field.status != 'found'
                or not isinstance(field.source, str) or not field.source.strip()
                or not isinstance(field.value, Decimal) or not field.value.is_finite() or field.value < 0):
            return False
    return True


def document_tax_audit(invoice):
    """Quadro fiscal da fatura, sem converter totais em deduções da compensação."""
    result = {}
    for key, labels in (('pis', ('PIS', 'PIS/PASEP')), ('cofins', ('COFINS',))):
        rows = tuple((index, row) for index, row in enumerate(invoice.tributos)
            if isinstance(row.get('tributo'), ExtractedField)
            and row['tributo'].status == 'found' and row['tributo'].value in labels
            and row['tributo'].source)
        values = {'base': None, 'rate': None, 'amount': None}
        status = 'AMBIGUOUS' if len(rows) > 1 else 'MISSING_DATA'
        if len(rows) == 1:
            for target, name in (('base', 'base_calculo'), ('rate', 'aliquota'), ('amount', 'valor')):
                field = rows[0][1].get(name)
                if (isinstance(field, ExtractedField) and field.status == 'found' and field.source
                        and isinstance(field.value, Decimal) and field.value.is_finite()):
                    values[target] = field.value
            field = rows[0][1].get('valor')
            status = ('RESOLVED' if values['amount'] is not None else 'AMBIGUOUS'
                      if field is not None and field.status == 'ambiguous' else 'MISSING_DATA')
        result[key] = {'source': 'DOCUMENT', 'status': status, **values,
                       'rate_unit': '%', 'evidence': tuple({'index': i, 'fields': row} for i, row in rows)}
    return result
