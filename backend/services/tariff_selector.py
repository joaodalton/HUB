"""Referência documental da concessionária; nunca seleciona a tarifa da empresa."""
from dataclasses import dataclass
from decimal import Decimal

from services.billing_calculation_contracts import (
    BillingCalculationIssue, BillingIssueSeverity, ResolvedBillingRule, TariffBasis, TariffSource,
)
from services.invoice_normalization_service import InvoiceNormalized
from services.document_tariff_resolver import (
    DocumentTariffEvidence as DocumentTariffCandidate,
    DocumentTariffResolver,
    REFERENCE_COMPOSITIONS,
    ResolutionStatus,
)


def _finite_decimal(value):
    return isinstance(value, Decimal) and value.is_finite()


@dataclass(frozen=True)
class TariffSelectionResult:
    value: Decimal | None
    source: TariffSource
    basis: TariffBasis
    document_label: str | None = None
    document_reference: str | None = None
    confidence: Decimal | None = None
    issues: tuple[BillingCalculationIssue, ...] = ()
    candidates: tuple[DocumentTariffCandidate, ...] = ()
    components: tuple[DocumentTariffCandidate, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, 'source', TariffSource(self.source))
        object.__setattr__(self, 'basis', TariffBasis(self.basis))
        if self.value is not None and not _finite_decimal(self.value):
            raise ValueError('Tarifa exige Decimal finito ou None.')
        if self.confidence is not None and (
            not _finite_decimal(self.confidence) or not 0 <= self.confidence <= 1
        ):
            raise ValueError('Confiança exige Decimal entre zero e um.')

    @property
    def concessionaria_reference_tariff_kwh(self):
        return self.value

    @property
    def warnings(self):
        return tuple(issue for issue in self.issues if issue.severity == BillingIssueSeverity.WARNING)


class TariffSelector:
    def select(self, invoice: InvoiceNormalized, rule: ResolvedBillingRule) -> TariffSelectionResult:
        if not isinstance(invoice, InvoiceNormalized) or not isinstance(rule, ResolvedBillingRule):
            raise TypeError('Selector exige InvoiceNormalized e ResolvedBillingRule.')
        identity = invoice.identity
        composition = REFERENCE_COMPOSITIONS.get((identity.parser_name, identity.parser_version,
                                                  identity.layout_name, identity.layout_version))
        if composition is not None:
            return self._compose_reference(invoice, rule, composition)
        issues = []
        candidates = []

        def issue(code, message, field=None):
            issues.append(BillingCalculationIssue(code, 'critical', message, field))

        def result(value=None):
            return TariffSelectionResult(value, TariffSource.INVOICE, rule.tariff_basis,
                                         issues=tuple(issues), candidates=tuple(candidates))

        # F6 não comprovou categorias documentais dessas bases. Não inferir por texto.
        if rule.tariff_basis in (TariffBasis.GD1, TariffBasis.GD2, TariffBasis.COMPENSATED):
            issue('unsupported_tariff_basis', 'Base sem suporte documental comprovado nesta versão.')
            return result()

        if rule.tariff_basis == TariffBasis.DOCUMENTED_COMPONENT:
            index = rule.energy_component_index
            if type(index) is not int or not 0 <= index < len(invoice.energy_components):
                issue('required_invoice_data_missing', 'Componente documental não encontrado.')
                return result()
            components = (invoice.energy_components[index],)
        else:
            components = []
            for component in invoice.energy_components:
                category = component.get('category')
                if category is not None and category.status == 'found' and category.value == 'consumed':
                    components.append(component)
                elif category is not None and category.status == 'ambiguous':
                    issue('ambiguous_tariff_basis', 'Categoria energética ambígua; não inferir consumo.')
            if not components:
                issue('required_invoice_data_missing', 'Nenhum componente de consumo comprovado.')
                return result()

        item_ids = set()
        for component in components:
            unit, amount, reference = (component.get(key) for key in ('unit', 'amount_kwh', 'item_index'))
            if (unit is None or unit.status != 'found' or unit.value != 'kWh'
                    or amount is None or amount.status != 'found' or not _finite_decimal(amount.value)):
                issue('required_invoice_data_missing', 'Componente exige unidade kWh e quantidade legível.')
                continue
            if (reference is None or reference.status != 'found' or type(reference.value) is not int
                    or not 0 <= reference.value < len(invoice.itens_documentais)):
                issue('invalid_document_reference', 'Referência de item inválida.')
                continue
            item_ids.add(reference.value)

        for row in invoice.tariffs_documented:
            reference = row.get('item_index')
            if (reference is None or reference.status != 'found' or type(reference.value) is not int
                    or not 0 <= reference.value < len(invoice.itens_documentais)):
                issue('invalid_document_reference', 'Tarifa sem referência válida ao item.')
                continue
            index = reference.value
            if index not in item_ids:
                continue
            label = invoice.itens_documentais[index].get('descricao_original')
            label_value = label.value if label is not None and label.status == 'found' else None
            if not isinstance(label_value, str) or not label_value.strip():
                issue('required_invoice_data_missing', 'Label original do item indisponível.')
                label_value = None
            for field in ('tarifa_unitaria', 'preco_unitario_com_tributos'):
                extracted = row.get(field)
                if extracted is None:
                    continue
                path = f'itens_documentais[{index}].{field}'
                status = extracted.status
                value = extracted.value if status == 'found' and _finite_decimal(extracted.value) else None
                if status == 'found' and value is None:
                    status = 'failed'
                candidates.append(DocumentTariffCandidate(
                    value, status, label_value, path, field, extracted.source, extracted.confidence,
                ))
                issues.extend(BillingCalculationIssue(w.code, w.severity.value, w.message, path)
                              for w in extracted.warnings)
                if status in ('failed', 'ambiguous'):
                    issue('unreadable_document_tariff' if status == 'failed' else 'ambiguous_document_tariff',
                          'Campo documental não pode ser selecionado.', path)

        found = [candidate for candidate in candidates if candidate.status == 'found']
        if len(found) > 1:
            issue('ambiguous_document_tariff', 'Múltiplas tarifas candidatas; nenhuma escolhida.')
        if not candidates or all(candidate.status == 'not_present' for candidate in candidates):
            issue('document_tariff_missing', 'Tarifa documental não presente para a base.')
        # Disponibilidade de uma coluna não define a referência da concessionária.
        issue('tariff_reference_representation_required',
              'Referência da concessionária exige critério explícito entre as colunas documentais.')
        return result()

    def _compose_reference(self, invoice, rule, composition):
        resolved = DocumentTariffResolver().resolve(invoice).full_tariff
        components = resolved.evidence
        issues = [BillingCalculationIssue(w.code, w.severity.value, w.message, w.field)
                  for w in resolved.issues if w.code not in {
                      'TARIFA_CHEIA_NAO_ENCONTRADA', 'COMPONENTE_TARIFARIO_INCOMPLETO',
                      'MULTIPLOS_CANDIDATOS_TARIFA_CHEIA', 'DIVERGENCIA_COMPONENTES_TARIFA',
                  }]
        if resolved.status != ResolutionStatus.VALID:
            issues.append(BillingCalculationIssue(
                'concessionaire_tariff_ambiguous' if resolved.status == ResolutionStatus.AMBIGUOUS
                else 'concessionaire_tariff_components_missing',
                'critical', 'Composição documental da referência não pôde ser resolvida.',
            ))
        value = resolved.value
        return TariffSelectionResult(value, TariffSource.INVOICE, rule.tariff_basis,
            document_label=' + '.join(c.document_label for c in components) if value is not None else None,
            document_reference=' + '.join(c.document_reference for c in components) if value is not None else None,
            confidence=resolved.confidence, issues=tuple(issues),
            candidates=tuple(components), components=tuple(components))
