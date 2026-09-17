"""Resolve tarifas comprovadas pelo documento, sem aplicar regra comercial."""
from dataclasses import dataclass
from decimal import Decimal, localcontext
from enum import Enum

from services.invoice_compensation import EnergyStatus as ResolutionStatus
from services.invoice_normalization_service import InvoiceNormalized
from services.invoice_parsers.schemas import ExtractedField, ExtractionIssue


REFERENCE_COMPOSITIONS = {
    ('copel', '1.3.0', 'danf3e', 'DANF3EA4B-V1.06'): (
        'energia_elet_consumo', 'energia_elet_uso_sistema',
    ),
}
FLAG_COMPONENTS = {'energia_cons_b_amarela'}


class DocumentTariffKind(str, Enum):
    FULL = 'full'
    COMPENSATION = 'compensation'
    UNKNOWN = 'unknown'


def _finite_decimal(value):
    return isinstance(value, Decimal) and value.is_finite()


def _sum_exact(values):
    with localcontext() as context:
        context.prec = max(v.adjusted() for v in values) - min(v.as_tuple().exponent for v in values) + len(str(len(values))) + 2
        return sum(values, Decimal(0))


def _issue(code, message, field=None):
    return ExtractionIssue(code, 'warning', message, field)


@dataclass(frozen=True)
class DocumentTariffEvidence:
    value: Decimal | None
    status: str
    document_label: str | None
    document_reference: str
    document_field: str
    document_source: str | None
    confidence: Decimal | None
    warnings: tuple[ExtractionIssue, ...] = ()

    def __post_init__(self):
        if self.value is not None and not _finite_decimal(self.value):
            raise ValueError('Evidência tarifária exige Decimal finito ou None.')
        if self.confidence is not None and (
            not _finite_decimal(self.confidence) or not 0 <= self.confidence <= 1
        ):
            raise ValueError('Confiança exige Decimal entre zero e um.')


@dataclass(frozen=True)
class ResolvedDocumentTariff:
    kind: DocumentTariffKind
    value: Decimal | None
    with_taxes: bool | None
    includes_flag: bool | None
    source_item_indexes: tuple[int, ...]
    confidence: Decimal | None
    status: ResolutionStatus
    issues: tuple[ExtractionIssue, ...]
    evidence: tuple[DocumentTariffEvidence, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, 'kind', DocumentTariffKind(self.kind))
        object.__setattr__(self, 'status', ResolutionStatus(self.status))
        if self.status == ResolutionStatus.VALID:
            if not _finite_decimal(self.value) or self.value < 0 or not self.source_item_indexes:
                raise ValueError('Tarifa VALID exige Decimal não negativo e origem documental.')
        elif self.value is not None:
            raise ValueError('Tarifa não VALID não pode fornecer valor.')
        if self.with_taxes is not None and type(self.with_taxes) is not bool:
            raise TypeError('with_taxes exige bool ou None.')
        if self.includes_flag is not None and type(self.includes_flag) is not bool:
            raise TypeError('includes_flag exige bool ou None.')
        if self.confidence is not None and (
            not _finite_decimal(self.confidence) or not 0 <= self.confidence <= 1
        ):
            raise ValueError('Confiança exige Decimal entre zero e um.')


@dataclass(frozen=True)
class ResolvedDocumentTariffs:
    full_tariff: ResolvedDocumentTariff | None
    compensation_tariff: ResolvedDocumentTariff | None
    status: ResolutionStatus
    issues: tuple[ExtractionIssue, ...]

    def __post_init__(self):
        object.__setattr__(self, 'status', ResolutionStatus(self.status))


class DocumentTariffResolver:
    def resolve(self, invoice: InvoiceNormalized) -> ResolvedDocumentTariffs:
        if not isinstance(invoice, InvoiceNormalized):
            raise TypeError('Resolver exige InvoiceNormalized.')
        full = self._resolve_full(invoice)
        compensation = self._resolve_compensation(invoice)
        statuses = {full.status, compensation.status}
        status = next((candidate for candidate in (
            ResolutionStatus.AMBIGUOUS, ResolutionStatus.UNSUPPORTED,
            ResolutionStatus.MISSING, ResolutionStatus.VALID,
        ) if candidate in statuses), ResolutionStatus.MISSING)
        return ResolvedDocumentTariffs(full, compensation, status, full.issues + compensation.issues)

    def _empty(self, kind, status, code, message, issues=(), evidence=()):
        combined = tuple(issues) + (_issue(code, message),)
        indexes = tuple(sorted({self._evidence_index(item) for item in evidence
                                if self._evidence_index(item) is not None}))
        return ResolvedDocumentTariff(kind, None, None, None, indexes, None,
                                      status, combined, tuple(evidence))

    @staticmethod
    def _evidence_index(evidence):
        prefix = 'itens_documentais['
        if not evidence.document_reference.startswith(prefix):
            return None
        try:
            return int(evidence.document_reference[len(prefix):].split(']', 1)[0])
        except (ValueError, IndexError):
            return None

    def _resolve_full(self, invoice):
        identity = invoice.identity
        composition = REFERENCE_COMPOSITIONS.get((identity.parser_name, identity.parser_version,
                                                  identity.layout_name, identity.layout_version))
        if composition is None:
            status = ResolutionStatus.UNSUPPORTED if invoice.tariffs_documented else ResolutionStatus.MISSING
            code = 'TARIFA_CHEIA_NAO_SUPORTADA' if status == ResolutionStatus.UNSUPPORTED else 'TARIFA_CHEIA_NAO_ENCONTRADA'
            return self._empty(DocumentTariffKind.FULL, status, code,
                               'Não há composição documental comprovada para a tarifa cheia.')

        issues, indexes = [], []
        for identifier in composition:
            matches = []
            for index, item in enumerate(invoice.itens_documentais):
                label = item.get('descricao_normalizada')
                if label is not None and label.status == 'ambiguous' and label.value == identifier:
                    issues.append(_issue('MULTIPLOS_CANDIDATOS_TARIFA_CHEIA',
                                         'Classificação documental ambígua.', f'itens_documentais[{index}]'))
                if label is not None and label.status == 'found' and label.value == identifier:
                    matches.append(index)
            if len(matches) > 1:
                issues.append(_issue('MULTIPLOS_CANDIDATOS_TARIFA_CHEIA',
                                     f'Múltiplos componentes {identifier}.'))
            elif not matches:
                issues.append(_issue('COMPONENTE_TARIFARIO_INCOMPLETO',
                                     f'Componente ausente: {identifier}.'))
            else:
                indexes.append(matches[0])

        if any(issue.code == 'MULTIPLOS_CANDIDATOS_TARIFA_CHEIA' for issue in issues):
            return self._empty(DocumentTariffKind.FULL, ResolutionStatus.AMBIGUOUS,
                               'DIVERGENCIA_COMPONENTES_TARIFA',
                               'Componentes da tarifa cheia não formam candidato único.', issues)
        if len(indexes) != len(composition):
            return self._empty(DocumentTariffKind.FULL, ResolutionStatus.MISSING,
                               'TARIFA_CHEIA_NAO_ENCONTRADA',
                               'Tarifa cheia exige todos os componentes documentais.', issues)

        evidence, evidence_issues, status = self._read_unit_tariffs(invoice, indexes)
        issues.extend(evidence_issues)
        if status != ResolutionStatus.VALID:
            code = ('MULTIPLOS_CANDIDATOS_TARIFA_CHEIA' if status == ResolutionStatus.AMBIGUOUS
                    else 'COMPONENTE_TARIFARIO_INCOMPLETO')
            return self._empty(DocumentTariffKind.FULL, status, code,
                               'Tarifa cheia não possui componentes unitários inequívocos.', issues, evidence)

        with_taxes, tax_issues = self._tax_state(invoice, evidence)
        includes_flag, flag_issues = self._flag_state(invoice)
        issues.extend(tax_issues + flag_issues)
        if flag_issues:
            includes_flag = None
        values = [item.value for item in evidence]
        confidence = self._confidence(evidence)
        return ResolvedDocumentTariff(
            DocumentTariffKind.FULL, _sum_exact(values), with_taxes, includes_flag,
            tuple(indexes), confidence, ResolutionStatus.VALID, tuple(issues), tuple(evidence),
        )

    def _resolve_compensation(self, invoice):
        energy = invoice.billing_energy_input
        if energy is None or energy.status == ResolutionStatus.UNSUPPORTED:
            return self._empty(DocumentTariffKind.COMPENSATION, ResolutionStatus.UNSUPPORTED,
                               'TARIFA_COMPENSACAO_NAO_SUPORTADA',
                               'Parser não comprova componentes de compensação neste layout.')
        if not energy.compensacoes:
            status = ResolutionStatus.AMBIGUOUS if energy.status == ResolutionStatus.AMBIGUOUS else ResolutionStatus.MISSING
            return self._empty(DocumentTariffKind.COMPENSATION, status,
                               'TARIFA_COMPENSACAO_NAO_ENCONTRADA',
                               'Nenhuma tarifa de compensação comprovada.', energy.issues)

        all_evidence, issues, candidate_values = [], list(energy.issues), []
        for event in energy.compensacoes:
            if event.status != ResolutionStatus.VALID:
                issues.extend(event.issues)
                continue
            kinds = {component.tipo for component in event.componentes}
            indexes = []
            for component in event.componentes:
                reference = component.energy_evidence.get('item_index')
                if reference is not None and reference.status == 'found' and type(reference.value) is int:
                    indexes.append(reference.value)
            if kinds != {'TE', 'TUSD'} or len(indexes) != 2 or len(set(indexes)) != 2:
                issues.append(_issue('DIVERGENCIA_COMPONENTES_TARIFA',
                                     'Compensação exige par TE/TUSD com origens distintas.'))
                continue
            evidence, event_issues, status = self._read_unit_tariffs(invoice, indexes)
            issues.extend(event_issues)
            all_evidence.extend(evidence)
            if status == ResolutionStatus.VALID:
                candidate_values.append((_sum_exact([item.value for item in evidence]), tuple(indexes), tuple(evidence)))

        if len(energy.compensacoes) > 1:
            return self._empty(DocumentTariffKind.COMPENSATION, ResolutionStatus.AMBIGUOUS,
                               'MULTIPLOS_CANDIDATOS_TARIFA_COMPENSACAO',
                               'Múltiplos eventos fornecem candidatos de compensação.', issues, all_evidence)
        if not candidate_values:
            status = ResolutionStatus.AMBIGUOUS if energy.status == ResolutionStatus.AMBIGUOUS or any(
                issue.code in ('DIVERGENCIA_COMPONENTES_TARIFA', 'MULTIPLOS_CANDIDATOS_TARIFA_COMPENSACAO')
                for issue in issues) else ResolutionStatus.MISSING
            return self._empty(DocumentTariffKind.COMPENSATION, status,
                               'COMPONENTE_TARIFARIO_INCOMPLETO',
                               'Tarifa de compensação exige par tarifário completo.', issues, all_evidence)

        value, indexes, evidence = candidate_values[0]
        with_taxes, tax_issues = self._tax_state(invoice, evidence)
        issues.extend(tax_issues)
        return ResolvedDocumentTariff(
            DocumentTariffKind.COMPENSATION, value, with_taxes, None, indexes,
            self._confidence(evidence), ResolutionStatus.VALID, tuple(issues), evidence,
        )

    def _read_unit_tariffs(self, invoice, indexes):
        evidence, issues = [], []
        status = ResolutionStatus.VALID
        for index in indexes:
            item = invoice.itens_documentais[index] if 0 <= index < len(invoice.itens_documentais) else {}
            label = item.get('descricao_original')
            unit = item.get('unidade')
            rows = []
            for row in invoice.tariffs_documented:
                reference = row.get('item_index')
                if reference is not None and reference.status == 'ambiguous' and reference.value == index:
                    status = ResolutionStatus.AMBIGUOUS
                    issues.append(_issue('DIVERGENCIA_COMPONENTES_TARIFA',
                                         'Referência tarifária ambígua.', f'itens_documentais[{index}]'))
                if reference is not None and reference.status == 'found' and type(reference.value) is int and reference.value == index:
                    rows.append(row)
            if len(rows) > 1:
                status = ResolutionStatus.AMBIGUOUS
                issues.append(_issue('DIVERGENCIA_COMPONENTES_TARIFA',
                                     'Múltiplas tarifas referenciam o mesmo item.', f'itens_documentais[{index}]'))
                continue
            tariff = rows[0].get('tarifa_unitaria') if rows else None
            path = f'itens_documentais[{index}].tarifa_unitaria'
            value = tariff.value if tariff is not None and tariff.status == 'found' and _finite_decimal(tariff.value) else None
            evidence.append(DocumentTariffEvidence(
                value, tariff.status.value if tariff is not None else 'not_present',
                label.value if label is not None and label.status == 'found' and isinstance(label.value, str) else None,
                path, 'tarifa_unitaria', tariff.source if tariff is not None else None,
                tariff.confidence if tariff is not None else None,
                tariff.warnings if tariff is not None else (),
            ))
            if tariff is not None:
                issues.extend(ExtractionIssue(w.code, w.severity, w.message, path, w.metadata)
                              for w in tariff.warnings)
            if (unit is None or unit.status != 'found' or unit.value != 'kWh'):
                status = ResolutionStatus.AMBIGUOUS
                issues.append(_issue('DIVERGENCIA_COMPONENTES_TARIFA',
                                     'Componente tarifário exige unidade kWh.', path))
            elif label is None or label.status != 'found' or not isinstance(label.value, str) or not label.value.strip():
                status = ResolutionStatus.AMBIGUOUS if label is not None and label.status == 'ambiguous' else (
                    status if status == ResolutionStatus.AMBIGUOUS else ResolutionStatus.MISSING)
                issues.append(_issue('DIVERGENCIA_COMPONENTES_TARIFA',
                                     'Componente tarifário exige label documental inequívoco.', path))
            elif (tariff is None or tariff.status == 'not_present'):
                if status != ResolutionStatus.AMBIGUOUS:
                    status = ResolutionStatus.MISSING
            elif tariff.status == 'ambiguous':
                status = ResolutionStatus.AMBIGUOUS
            elif value is None or not isinstance(tariff.source, str) or not tariff.source.strip():
                if status != ResolutionStatus.AMBIGUOUS:
                    status = ResolutionStatus.MISSING
        return tuple(evidence), issues, status

    @staticmethod
    def _confidence(evidence):
        values = [item.confidence for item in evidence]
        return min(values) if values and all(value is not None for value in values) else None

    @staticmethod
    def _tax_state(invoice, evidence):
        states, issues = [], []
        for item in evidence:
            index = DocumentTariffResolver._evidence_index(item)
            rows = [row for row in invoice.tariffs_documented
                    if (reference := row.get('item_index')) is not None
                    and reference.status == 'found' and reference.value == index]
            taxed = rows[0].get('preco_unitario_com_tributos') if len(rows) == 1 else None
            if taxed is not None and taxed.status == 'found' and _finite_decimal(taxed.value):
                states.append(True)
            elif taxed is None or taxed.status == 'not_present':
                states.append(False)
            else:
                states.append(None)
        if states and all(state is True for state in states):
            return False, []  # tarifa_unitaria é a variante escolhida; a tributada está separada.
        if any(state is None for state in states) or any(states) and not all(states):
            issues.append(_issue('TRIBUTACAO_TARIFA_AMBIGUA',
                                 'Não foi possível provar uma única representação tributária.'))
        return None, issues

    @staticmethod
    def _flag_state(invoice):
        found, ambiguous = 0, False
        for item in invoice.itens_documentais:
            label = item.get('descricao_normalizada')
            if label is None:
                continue
            if label.status == 'found' and label.value in FLAG_COMPONENTS:
                found += 1
            elif label.status == 'ambiguous' and label.value in FLAG_COMPONENTS:
                ambiguous = True
        if ambiguous or found > 1:
            return None, [_issue('BANDEIRA_AMBIGUA', 'Item de bandeira não é inequívoco.')]
        return (False, []) if found == 1 else (None, [])
