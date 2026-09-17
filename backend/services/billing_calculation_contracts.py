"""C0: contratos comerciais e matemáticos; nenhuma implementação de cálculo."""
from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
import json
import re

from services.invoice_normalization_service import InvoiceNormalized, json_safe


CALCULATION_ENGINE_VERSION = '1.0'


class BillingRuleScope(str, Enum):
    COMPANY = 'company'
    CLIENT = 'client'
    CONSUMER_UNIT = 'consumer_unit'


class CalculationMethod(str, Enum):
    ENERGIA_COMPENSADA = 'energia_compensada'
    ECONOMIA_GERADA = 'economia_gerada'
    VALOR_TOTAL_FATURA = 'valor_total_fatura'
    TARIFA_FIXA = 'tarifa_fixa'
    TARIFA_FIXA_COM_DESCONTO = 'tarifa_fixa_com_desconto'
    TARIFA_ESPECIFICA = 'tarifa_especifica'
    ENERGIA_RECEBIDA = 'energia_recebida'


class TariffSource(str, Enum):
    INVOICE = 'invoice'
    MANUAL = 'manual'


class DiscountType(str, Enum):
    PERCENTAGE = 'percentage'
    FIXED = 'fixed'
    NONE = 'none'


class TariffBasis(str, Enum):
    CONSUMED = 'consumed'
    COMPENSATED = 'compensated'
    GD1 = 'gd1'
    GD2 = 'gd2'
    DOCUMENTED_COMPONENT = 'documented_component'


class BillingMode(str, Enum):
    AUTO = 'auto'
    UNIFIED = 'unified'
    SEPARATE = 'separate'


class DueDateBasis(str, Enum):
    INVOICE_DUE_DATE = 'invoice_due_date'
    INVOICE_ISSUE_DATE = 'invoice_issue_date'
    READING_DATE = 'reading_date'
    CALCULATION_DATE = 'calculation_date'


class BillingIssueSeverity(str, Enum):
    INFO = 'info'
    WARNING = 'warning'
    CRITICAL = 'critical'


class CalculationBlockCode(str, Enum):
    REQUIRED_TAX_DATA_MISSING = 'required_tax_data_missing'
    BASE_TARIFF_WITHOUT_FLAG_MISSING = 'base_tariff_without_flag_missing'
    REQUIRED_ICMS_DATA_MISSING = 'required_icms_data_missing'
    REQUIRED_ENERGY_DATA_MISSING = 'required_energy_data_missing'
    TARIFF_REFERENCE_REPRESENTATION_REQUIRED = 'tariff_reference_representation_required'
    CONCESSIONAIRE_TARIFF_COMPONENTS_MISSING = 'concessionaire_tariff_components_missing'
    CONCESSIONAIRE_TARIFF_AMBIGUOUS = 'concessionaire_tariff_ambiguous'


class ComponentTreatment(str, Enum):
    NOT_EVALUATED = 'not_evaluated'
    APPLIED = 'applied'
    EXCLUDED = 'excluded'
    NOT_APPLICABLE = 'not_applicable'
    BLOCKED = 'blocked'


def _positive_id(value):
    if type(value) is not int or value <= 0:
        raise ValueError('Identificador deve ser inteiro positivo.')


def _decimal(value):
    if value is not None and (not isinstance(value, Decimal) or not value.is_finite()):
        raise ValueError('Valor deve ser Decimal finito ou None; sem coerção/rounding.')


@dataclass(frozen=True)
class BillingCalculationContext:
    empresa_id: int
    client_id: int
    consumer_unit_id: int
    fatura_concessionaria_id: int
    competencia: str
    calculation_timestamp: datetime | None = None

    def __post_init__(self):
        for value in (self.empresa_id, self.client_id, self.consumer_unit_id, self.fatura_concessionaria_id):
            _positive_id(value)
        if not isinstance(self.competencia, str) or not re.fullmatch(r'(?!0000)[0-9]{4}-(?:0[1-9]|1[0-2])', self.competencia):
            raise ValueError('Competência deve ser YYYY-MM.')
        if self.calculation_timestamp is not None and not isinstance(self.calculation_timestamp, datetime):
            raise TypeError('Timestamp deve ser datetime; nunca gerado implicitamente.')


@dataclass(frozen=True)
class TariffConfiguration:
    """Parâmetros comerciais; nunca valores extraídos da concessionária."""
    company_tariff: Decimal | None = None
    tariff_hfp: Decimal | None = None
    tariff_hp: Decimal | None = None

    def __post_init__(self):
        for value in (self.company_tariff, self.tariff_hfp, self.tariff_hp):
            _decimal(value)


@dataclass(frozen=True)
class GracePeriod:
    """Política reutilizável. Origem temporal pertence ao target, nunca ao grupo."""
    enabled: bool | None = None
    without_discount: bool | None = None
    duration_months: int | None = None

    def __post_init__(self):
        for value in (self.enabled, self.without_discount):
            if value is not None and type(value) is not bool:
                raise ValueError('Carência exige booleano ou None.')
        if self.duration_months is not None and (
            type(self.duration_months) is not int or not 1 <= self.duration_months <= 2147483647
        ):
            raise ValueError('Duração da carência exige meses inteiros positivos ou None.')
        if self.enabled is not True and (self.without_discount is not None or self.duration_months is not None):
            raise ValueError('Parâmetros de carência exigem habilitação explícita.')

    @property
    def requires_temporal_definition(self):
        # Mesmo com duração, a origem por target ainda precisa ser comprovada.
        return self.enabled is True


@dataclass(frozen=True)
class BillingModifiers:
    exclude_pis_cofins: bool | None = None
    icms_policy: str | None = None
    exclude_tariff_flag: bool | None = None
    grace_period: GracePeriod = field(default_factory=GracePeriod)
    recurring_additional_cost: Decimal | None = None

    def __post_init__(self):
        for value in (self.exclude_pis_cofins, self.exclude_tariff_flag):
            if value is not None and type(value) is not bool:
                raise ValueError('Modificador exige booleano ou None.')
        if self.icms_policy not in (None, 'exclude'):
            raise ValueError('Política ICMS suportada: exclude (SEM ICMS) ou None.')
        if not isinstance(self.grace_period, GracePeriod):
            raise TypeError('Carência exige GracePeriod.')
        _decimal(self.recurring_additional_cost)


def validate_commercial_method(method, tariff, discount_type, discount_value):
    """Somente requisitos confirmados; não define fórmula nem reinterpreta legados."""
    if method in (CalculationMethod.TARIFA_ESPECIFICA, CalculationMethod.TARIFA_FIXA_COM_DESCONTO):
        if tariff.company_tariff is None:
            raise ValueError('Método exige companyTariff.')
    if method == CalculationMethod.TARIFA_FIXA_COM_DESCONTO:
        if discount_type != DiscountType.PERCENTAGE or discount_value is None:
            raise ValueError('tarifa_fixa_com_desconto exige desconto percentage explícito.')


@dataclass(frozen=True)
class ResolvedBillingRule:
    rule_id: int
    rule_name: str
    rule_version: str
    source_scope: BillingRuleScope
    source_id: int
    calculation_method: CalculationMethod
    tariff_source: TariffSource
    discount_type: DiscountType
    tariff_basis: TariffBasis
    billing_mode: BillingMode
    due_date_basis: DueDateBasis
    due_date_offset_days: int
    manual_tariff: Decimal | None = None
    discount_value: Decimal | None = None
    monthly_interest: Decimal | None = None
    fine_percentage: Decimal | None = None
    energy_component_index: int | None = None
    metadata: dict[str, str] = field(default_factory=dict)
    tariff_configuration: TariffConfiguration | None = None
    billing_modifiers: BillingModifiers = field(default_factory=BillingModifiers)

    def __post_init__(self):
        _positive_id(self.rule_id)
        _positive_id(self.source_id)
        for value in (self.rule_name, self.rule_version):
            if not isinstance(value, str) or not value.strip():
                raise ValueError('Regra exige nome e versão.')
        for name, enum in (
            ('source_scope', BillingRuleScope), ('calculation_method', CalculationMethod),
            ('tariff_source', TariffSource), ('discount_type', DiscountType),
            ('tariff_basis', TariffBasis), ('billing_mode', BillingMode), ('due_date_basis', DueDateBasis),
        ):
            object.__setattr__(self, name, enum(getattr(self, name)))
        for value in (self.manual_tariff, self.discount_value, self.monthly_interest, self.fine_percentage):
            _decimal(value)
        configuration = self.tariff_configuration
        if configuration is None:
            configuration = TariffConfiguration(company_tariff=self.manual_tariff)
        if not isinstance(configuration, TariffConfiguration):
            raise TypeError('Tarifa comercial exige TariffConfiguration.')
        if self.manual_tariff is not None and self.manual_tariff != configuration.company_tariff:
            raise ValueError('manual_tariff e company_tariff devem representar o mesmo valor.')
        object.__setattr__(self, 'manual_tariff', configuration.company_tariff)
        object.__setattr__(self, 'tariff_configuration', configuration)
        if not isinstance(self.billing_modifiers, BillingModifiers):
            raise TypeError('Modificadores exigem BillingModifiers.')
        validate_commercial_method(self.calculation_method, configuration, self.discount_type, self.discount_value)
        if self.tariff_source == TariffSource.MANUAL and self.manual_tariff is None:
            raise ValueError('manual_tariff obrigatório para fonte manual.')
        if self.discount_type != DiscountType.NONE and self.discount_value is None:
            raise ValueError('discount_value obrigatório para desconto configurado.')
        if type(self.due_date_offset_days) is not int:
            raise TypeError('Offset deve ser inteiro, positivo, zero ou negativo.')
        if self.energy_component_index is not None and (
            type(self.energy_component_index) is not int or self.energy_component_index < 0
        ):
            raise ValueError('Índice de componente deve ser inteiro não negativo.')
        if self.tariff_basis == TariffBasis.DOCUMENTED_COMPONENT and self.energy_component_index is None:
            raise ValueError('Base componente exige referência explícita.')
        if self.tariff_basis != TariffBasis.DOCUMENTED_COMPONENT and self.energy_component_index is not None:
            raise ValueError('Referência de componente exige a base correspondente.')
        if not isinstance(self.metadata, dict) or any(
            not isinstance(k, str) or not isinstance(v, str) for k, v in self.metadata.items()
        ):
            raise TypeError('Metadata exige chaves/valores textuais.')
        object.__setattr__(self, 'metadata', dict(self.metadata))


@dataclass(frozen=True, init=False)
class BillingRuleSnapshot:
    """Captura independente e imutável; to_dict sempre devolve uma cópia."""
    payload_json: str

    def __init__(self, rule: ResolvedBillingRule):
        if not isinstance(rule, ResolvedBillingRule):
            raise TypeError('Snapshot exige regra resolvida.')
        object.__setattr__(self, 'payload_json', json.dumps(
            json_safe(rule), sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':'),
        ))

    def to_dict(self):
        return json.loads(self.payload_json)


@dataclass(frozen=True)
class BillingCalculationIssue:
    code: str
    severity: BillingIssueSeverity
    message: str
    field: str | None = None

    def __post_init__(self):
        object.__setattr__(self, 'severity', BillingIssueSeverity(self.severity))
        if not self.code.strip() or not self.message.strip():
            raise ValueError('Issue exige código e mensagem.')


def required_document_value(value: Decimal | None, *, source: str | None,
                            missing_code: CalculationBlockCode) -> BillingCalculationIssue | None:
    """Pré-condição apenas. Chamador fornece somente evidência documental validada.

    Falho/ambíguo/não comprovado deve chegar como None. Zero documental é distinto
    de ausência. Não extrai, reconstrói ou decide quais dados uma strategy requer.
    """
    code = CalculationBlockCode(missing_code)
    _decimal(value)
    if value is None or not isinstance(source, str) or not source.strip():
        return BillingCalculationIssue(code.value, BillingIssueSeverity.CRITICAL,
                                       'Dado documental obrigatório não comprovado.')
    return None


@dataclass(frozen=True)
class CalculationMemory:
    """Auditoria fornecida pela strategy, sem gerar valores ou políticas.

    Método/parâmetros originais estão no rule_snapshot; energia/base/desconto
    efetivo/adicionais/resultado estão no resultado. Aqui ficam origem e tratamentos.
    """
    energy_source: str | None = None
    energy_reference: str | None = None
    company_tariff_used: Decimal | None = None
    concessionaria_reference_tariff: Decimal | None = None
    concessionaria_reference_source: str | None = None
    concessionaria_reference_components: tuple[dict, ...] = ()
    pis_cofins_treatment: ComponentTreatment = ComponentTreatment.NOT_EVALUATED
    pis_cofins_amount: Decimal | None = None
    icms_treatment: ComponentTreatment = ComponentTreatment.NOT_EVALUATED
    icms_amount: Decimal | None = None
    tariff_flag_treatment: ComponentTreatment = ComponentTreatment.NOT_EVALUATED
    tariff_flag_amount: Decimal | None = None
    original_discount_amount: Decimal | None = None
    grace_state: str = 'not_evaluated'
    grace_start: date | None = None
    grace_source: str | None = None
    recurring_additional_cost: Decimal | None = None
    discount_percentage: Decimal | None = None
    effective_company_tariff: Decimal | None = None
    net_amount_before_rounding: Decimal | None = None
    monetary_rounding: str | None = None
    desconto_aplicado: bool | None = None

    def __post_init__(self):
        if self.desconto_aplicado is not None and type(self.desconto_aplicado) is not bool:
            raise ValueError('desconto_aplicado exige booleano ou None.')
        if not isinstance(self.concessionaria_reference_components, tuple) or any(
            not isinstance(component, dict) for component in self.concessionaria_reference_components
        ):
            raise TypeError('Componentes da referência exigem tupla de mapas documentais.')
        json_safe(self.concessionaria_reference_components)
        object.__setattr__(self, 'concessionaria_reference_components', deepcopy(self.concessionaria_reference_components))
        for name in ('company_tariff_used', 'concessionaria_reference_tariff', 'pis_cofins_amount',
                     'icms_amount', 'tariff_flag_amount', 'original_discount_amount', 'recurring_additional_cost',
                     'discount_percentage', 'effective_company_tariff', 'net_amount_before_rounding'):
            _decimal(getattr(self, name))
        for name in ('pis_cofins_treatment', 'icms_treatment', 'tariff_flag_treatment'):
            object.__setattr__(self, name, ComponentTreatment(getattr(self, name)))
        for name in ('energy_source', 'energy_reference', 'concessionaria_reference_source', 'grace_source'):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError('Origem de auditoria exige texto não vazio ou None.')
        if self.grace_state not in ('not_evaluated', 'active', 'inactive', 'not_applicable', 'blocked'):
            raise ValueError('Estado de carência inválido.')
        if self.grace_start is not None and type(self.grace_start) is not date:
            raise ValueError('Origem temporal exige data explícita do target.')
        if self.grace_start is not None and self.grace_source is None:
            raise ValueError('Data de carência exige origem auditável do target.')


@dataclass(frozen=True)
class BillingCalculationResult:
    context: BillingCalculationContext
    rule_snapshot: BillingRuleSnapshot
    calculation_version: str = field(default=CALCULATION_ENGINE_VERSION, init=False)
    energy_base_kwh: Decimal | None = None
    consumo_kwh: Decimal | None = None
    gd1_kwh: Decimal | None = None
    gd2_kwh: Decimal | None = None
    energia_compensada_kwh: Decimal | None = None
    tariff_value: Decimal | None = None
    gross_base: Decimal | None = None
    discount_amount: Decimal | None = None
    additions_amount: Decimal | None = None
    hub_amount: Decimal | None = None
    issues: tuple[BillingCalculationIssue, ...] = ()
    calculation_memory: dict | CalculationMemory = field(default_factory=CalculationMemory)

    def __post_init__(self):
        if not isinstance(self.context, BillingCalculationContext) or not isinstance(self.rule_snapshot, BillingRuleSnapshot):
            raise TypeError('Resultado exige contexto e snapshot tipados.')
        for name in ('energy_base_kwh', 'consumo_kwh', 'gd1_kwh', 'gd2_kwh', 'energia_compensada_kwh',
                     'tariff_value', 'gross_base', 'discount_amount', 'additions_amount', 'hub_amount'):
            _decimal(getattr(self, name))
        if any(not isinstance(i, BillingCalculationIssue) for i in self.issues):
            raise TypeError('Issues financeiras não são issues de extração.')
        object.__setattr__(self, 'issues', tuple(self.issues))
        if not isinstance(self.calculation_memory, (dict, CalculationMemory)):
            raise TypeError('Memória exige CalculationMemory ou mapa legado serializável.')
        json_safe(self.calculation_memory)
        object.__setattr__(self, 'calculation_memory', deepcopy(self.calculation_memory))

    @property
    def warnings(self):
        return tuple(i for i in self.issues if i.severity == BillingIssueSeverity.WARNING)

    def to_dict(self):
        payload = json_safe(self)
        snapshot = self.rule_snapshot.to_dict()
        payload['rule_snapshot'] = snapshot
        # Identidade/fonte derivam do snapshot, sem duplicação contraditória.
        payload.update({name: snapshot[name] for name in ('rule_id', 'rule_name', 'tariff_source', 'tariff_basis')})
        payload['rule_source_scope'] = snapshot['source_scope']
        payload['fatura_concessionaria_id'] = self.context.fatura_concessionaria_id
        payload['competencia'] = self.context.competencia
        payload['warnings'] = json_safe(self.warnings)
        return payload


class BillingCalculationEngine(ABC):
    @abstractmethod
    def calculate(self, *, invoice: InvoiceNormalized, rule: ResolvedBillingRule,
                  context: BillingCalculationContext) -> BillingCalculationResult:
        """Contrato apenas; estratégias reais serão implementadas em C5.

        Compensação usa somente invoice.billing_energy_input.require_valid().
        Engine nunca interpreta descrições/linhas Copel nem soma itens brutos.
        """
        raise NotImplementedError


class BillingCalculationStrategy(BillingCalculationEngine):
    @property
    @abstractmethod
    def method(self) -> CalculationMethod:
        raise NotImplementedError
