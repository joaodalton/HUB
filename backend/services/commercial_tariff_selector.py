"""Seleciona a tarifa comercial por evento sem calcular cobranca."""
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from services.billing_calculation_contracts import (
    BillingCalculationIssue,
    BillingIssueSeverity,
    BillingRuleSnapshot,
    CalculationMethod,
    ResolvedBillingRule,
    TariffSource,
)
from services.document_tariff_resolver import (
    ResolvedCompensationTariffEvent,
    ResolvedDocumentTariff,
    ResolvedDocumentTariffs,
    ResolutionStatus,
)
from services.invoice_normalization_service import json_safe


class CommercialTariffSource(str, Enum):
    CONFIGURED_FIXED = 'configured_fixed'
    CONFIGURED_SPECIFIC = 'configured_specific'
    DOCUMENT_FULL = 'document_full'
    DOCUMENT_COMPENSATION = 'document_compensation'


def _valid_tariff(value):
    return isinstance(value, Decimal) and value.is_finite() and value >= 0


def _issue(code, message):
    return BillingCalculationIssue(code, BillingIssueSeverity.CRITICAL, message)


@dataclass(frozen=True)
class SelectedCommercialTariff:
    event: ResolvedCompensationTariffEvent
    source_kind: CommercialTariffSource
    selected_tariff: Decimal | None
    document_full_tariff: Decimal | None
    document_compensation_tariff: Decimal | None
    includes_flag: bool | None
    with_taxes: bool | None
    status: ResolutionStatus
    issues: tuple[BillingCalculationIssue, ...]
    rule_snapshot: BillingRuleSnapshot

    def __post_init__(self):
        if not isinstance(self.event, ResolvedCompensationTariffEvent):
            raise TypeError('Selecao comercial exige evento documental.')
        object.__setattr__(self, 'source_kind', CommercialTariffSource(self.source_kind))
        object.__setattr__(self, 'status', ResolutionStatus(self.status))
        if not isinstance(self.rule_snapshot, BillingRuleSnapshot):
            raise TypeError('Selecao comercial exige snapshot da regra.')
        for value in (
            self.selected_tariff,
            self.document_full_tariff,
            self.document_compensation_tariff,
        ):
            if value is not None and not _valid_tariff(value):
                raise ValueError('Tarifa exige Decimal finito nao negativo ou None.')
        if self.status == ResolutionStatus.VALID:
            if self.selected_tariff is None:
                raise ValueError('Selecao VALID exige tarifa.')
        elif self.selected_tariff is not None:
            raise ValueError('Selecao nao VALID nao pode fornecer tarifa.')
        for value in (self.includes_flag, self.with_taxes):
            if value is not None and type(value) is not bool:
                raise TypeError('Evidencia tarifaria exige bool ou None.')
        if any(not isinstance(item, BillingCalculationIssue) for item in self.issues):
            raise TypeError('Issues da selecao devem ser financeiras.')
        object.__setattr__(self, 'issues', tuple(self.issues))

    def to_dict(self):
        payload = json_safe(self)
        payload['rule_snapshot'] = self.rule_snapshot.to_dict()
        return payload


class CommercialTariffSelector:
    """Aplica somente a politica de escolha; nao calcula valor monetario."""

    def select(self, tariffs: ResolvedDocumentTariffs,
               rule: ResolvedBillingRule) -> tuple[SelectedCommercialTariff, ...]:
        if not isinstance(tariffs, ResolvedDocumentTariffs):
            raise TypeError('Seletor exige ResolvedDocumentTariffs.')
        if not isinstance(rule, ResolvedBillingRule):
            raise TypeError('Seletor exige ResolvedBillingRule.')
        snapshot = BillingRuleSnapshot(rule)
        source = self._source(rule)
        return tuple(self._select_event(event, tariffs.full_tariff, rule, snapshot, source)
                     for event in tariffs.compensation_tariff_events)

    def _select_event(self, event, full, rule, snapshot, source):
        full_value = self._document_value(full)
        compensation_value = event.combined_tariff if event.status == ResolutionStatus.VALID else None
        if event.status != ResolutionStatus.VALID:
            return self._result(
                event, source, None, full_value, compensation_value,
                event.includes_flag, event.with_taxes, event.status,
                (_issue('invalid_compensation_tariff_event',
                        'Evento documental invalido bloqueia a selecao.'),), snapshot,
            )

        if source in (CommercialTariffSource.CONFIGURED_FIXED,
                      CommercialTariffSource.CONFIGURED_SPECIFIC):
            value = rule.tariff_configuration.company_tariff
            if not _valid_tariff(value):
                status = ResolutionStatus.MISSING if value is None else ResolutionStatus.UNSUPPORTED
                return self._result(
                    event, source, None, full_value, compensation_value, None, None,
                    status, (_issue('configured_tariff_missing',
                                    'Tarifa comercial configurada nao esta disponivel.'),), snapshot,
                )
            flag_status, flag_issues = self._validate_flag(
                rule.billing_modifiers.exclude_tariff_flag, None,
            )
            return self._result(
                event, source, value if flag_status == ResolutionStatus.VALID else None,
                full_value, compensation_value, None, None,
                flag_status, flag_issues, snapshot,
            )

        if source == CommercialTariffSource.DOCUMENT_FULL:
            value = full_value
            status = full.status if full is not None else ResolutionStatus.MISSING
            includes_flag = full.includes_flag if full is not None else None
            with_taxes = full.with_taxes if full is not None else None
        else:
            value = compensation_value
            status = event.status
            includes_flag = event.includes_flag
            with_taxes = event.with_taxes

        if status != ResolutionStatus.VALID or value is None:
            return self._result(
                event, source, None, full_value, compensation_value,
                includes_flag, with_taxes, status,
                (_issue('required_document_tariff_missing',
                        'Tarifa documental exigida pela regra nao esta disponivel.'),), snapshot,
            )

        flag_status, flag_issues = self._validate_flag(
            rule.billing_modifiers.exclude_tariff_flag, includes_flag,
        )
        return self._result(
            event, source, value if flag_status == ResolutionStatus.VALID else None,
            full_value, compensation_value, includes_flag, with_taxes,
            flag_status, flag_issues, snapshot,
        )

    @staticmethod
    def _source(rule):
        if rule.calculation_method == CalculationMethod.TARIFA_FIXA:
            return CommercialTariffSource.CONFIGURED_FIXED
        if rule.calculation_method == CalculationMethod.TARIFA_ESPECIFICA:
            return CommercialTariffSource.CONFIGURED_SPECIFIC
        if rule.calculation_method != CalculationMethod.ENERGIA_COMPENSADA:
            raise ValueError('Metodo ainda nao suporta selecao comercial por evento.')
        if rule.tariff_source != TariffSource.INVOICE:
            raise ValueError('Selecao documental exige tariff_source invoice.')
        if rule.billing_modifiers.icms_policy == 'exclude':
            return CommercialTariffSource.DOCUMENT_COMPENSATION
        return CommercialTariffSource.DOCUMENT_FULL

    @staticmethod
    def _document_value(tariff: ResolvedDocumentTariff | None):
        if tariff is None or tariff.status != ResolutionStatus.VALID:
            return None
        return tariff.value

    @staticmethod
    def _validate_flag(exclude, documented):
        if exclude is None:
            return ResolutionStatus.VALID, ()
        if documented is None:
            return ResolutionStatus.MISSING, (
                _issue('tariff_flag_evidence_missing',
                       'A regra exige variante de bandeira sem evidencia documental.'),
            )
        if documented is not (not exclude):
            return ResolutionStatus.UNSUPPORTED, (
                _issue('tariff_flag_incompatible',
                       'A variante documental de bandeira e incompativel com a regra.'),
            )
        return ResolutionStatus.VALID, ()

    @staticmethod
    def _result(event, source, selected, full, compensation, includes_flag,
                with_taxes, status, issues, snapshot):
        return SelectedCommercialTariff(
            event, source, selected, full, compensation, includes_flag,
            with_taxes, status, issues, snapshot,
        )
