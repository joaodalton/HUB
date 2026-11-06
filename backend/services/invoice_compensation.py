"""Normalização física de compensação. Não interpreta labels nem regras comerciais."""
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal, localcontext
from enum import Enum
import re

from services.invoice_parsers.schemas import ExtractedField, ExtractionIssue, FieldMap, ParserIdentity


class EnergyStatus(str, Enum):
    VALID = 'VALID'
    AMBIGUOUS = 'AMBIGUOUS'
    MISSING = 'MISSING'
    UNSUPPORTED = 'UNSUPPORTED'


@dataclass(frozen=True)
class ComponenteCompensacao:
    tipo: str
    quantidade_original_kwh: Decimal | None
    tarifa_r_kwh: ExtractedField | None
    valor_r: ExtractedField | None
    documento: FieldMap
    source: str
    energy_evidence: FieldMap


@dataclass(frozen=True)
class CompensacaoNormalizada:
    origem: str | None
    posto: str | None
    classificacao_gd: str
    mes_origem: str | None
    contexto_documental: str
    quantidade_kwh: Decimal | None
    componentes: tuple[ComponenteCompensacao, ...]
    source: tuple[str, ...]
    confidence: Decimal | None
    status: EnergyStatus
    issues: tuple[ExtractionIssue, ...]

    def __post_init__(self):
        object.__setattr__(self, 'status', EnergyStatus(self.status))
        value = self.quantidade_kwh
        if self.status == EnergyStatus.VALID:
            if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
                raise ValueError('Compensação VALID exige Decimal não negativo.')
            if (len(self.componentes) != 2 or {c.tipo for c in self.componentes} != {'TE', 'TUSD'}
                    or any(not isinstance(c.quantidade_original_kwh, Decimal)
                           or not c.quantidade_original_kwh.is_finite()
                           or c.quantidade_original_kwh.copy_abs() != value for c in self.componentes)):
                raise ValueError('Compensação VALID exige par TE/TUSD consistente.')
        elif value is not None:
            raise ValueError('Compensação inválida não fornece quantidade.')

    @property
    def cobravel_ouc_mpt(self):
        return self.origem == 'OUTRA_UC' and self.posto == 'MESMO_POSTO'


@dataclass(frozen=True)
class BillingEnergyInput:
    energia_compensada_cobravel_kwh: Decimal | None
    compensacoes: tuple[CompensacaoNormalizada, ...]
    status: EnergyStatus
    issues: tuple[ExtractionIssue, ...]
    source: ParserIdentity
    competencia: str | None
    fatura_concessionaria_id: int | None = None

    def __post_init__(self):
        object.__setattr__(self, 'status', EnergyStatus(self.status))
        value = self.energia_compensada_cobravel_kwh
        if self.status == EnergyStatus.VALID:
            billable = tuple(c for c in self.compensacoes if c.cobravel_ouc_mpt)
            if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
                raise ValueError('Energia VALID exige Decimal não negativo.')
            if not billable or any(c.status != EnergyStatus.VALID for c in billable):
                raise ValueError('Energia VALID exige compensações OUC/MPT válidas.')
            if value != _sum_exact([c.quantidade_kwh for c in billable]):
                raise ValueError('Energia cobrável deve derivar somente das compensações OUC/MPT.')
        elif value is not None:
            raise ValueError('Energia não VALID não pode fornecer quantidade cobrável.')

    def require_valid(self):
        if self.status != EnergyStatus.VALID:
            raise ValueError(f'required_energy_data_missing:{self.status.value}')
        return self.energia_compensada_cobravel_kwh


def _sum_exact(values):
    with localcontext() as context:
        context.prec = max(v.adjusted() for v in values) - min(v.as_tuple().exponent for v in values) + len(str(len(values))) + 2
        return sum(values, Decimal(0))


def normalize_compensations(parsed, competencia, fatura_id=None):
    issues, groups = [], {}

    def issue(code, message):
        return ExtractionIssue(code, 'warning', message, 'energia_compensada_cobravel_kwh')

    if not parsed.compensation_supported:
        return BillingEnergyInput(None, (), EnergyStatus.UNSUPPORTED,
            (issue('COMPENSACAO_NAO_SUPORTADA', 'Parser não comprova compensações neste layout.'),),
            parsed.identity, competencia, fatura_id)

    for row in parsed.energy_components:
        category = row.get('category')
        if category is None or category.status != 'found':
            issues.append(issue('COMPENSACAO_CATEGORIA_INDEFINIDA', 'Categoria energética não comprovada.'))
            continue
        if category.value != 'compensated':
            continue  # consumo, injeção, saldo, demanda e planejamento não são compensação
        try:
            def value(name, optional=False):
                field = row.get(name)
                if optional and (field is None or field.status == 'not_present'):
                    return None
                if (field is None or field.status != 'found' or not isinstance(field.source, str)
                        or not field.source.strip()):
                    raise ValueError(f'Campo {name} não comprovado.')
                return field.value

            origin = value('origin', True)
            origin = {'MUC': 'MESMA_UC', 'OUC': 'OUTRA_UC', None: None}[origin]
            period = value('period', True)
            period = {'MPT': 'MESMO_POSTO', 'OPT': 'OUTRO_POSTO', None: None}[period]
            if origin is None or period is None:
                raise ValueError('Origem e posto da compensação não comprovados.')
            gd = value('gd_classification', True)
            gd = 'UNKNOWN' if gd is None else gd
            if gd not in ('GD_I', 'GD_II', 'GD_III', 'UNKNOWN'):
                raise ValueError('GD não reconhecido.')
            month = value('credit_month', True)
            if month is not None and (not isinstance(month, str) or not re.fullmatch(r'(?!0000)[0-9]{4}-(0[1-9]|1[0-2])', month)):
                raise ValueError('Mês de origem inválido.')
            context = value('compensation_context')
            kind = value('tariff_component')
            index = value('item_index')
            if not isinstance(context, str) or not context.strip() or kind not in ('TE', 'TUSD'):
                raise ValueError('Contexto/componente não comprovado.')
            if type(index) is not int or not 0 <= index < len(parsed.itens):
                raise ValueError('Referência documental inválida.')
            key = (origin, period, gd, month, context)
            groups.setdefault(key, []).append((kind, row, index))
        except (ValueError, KeyError, TypeError) as exc:
            issues.append(issue('COMPENSACAO_IDENTIDADE_INDEFINIDA', str(exc)))

    events = []
    used_items = set()
    for key, rows in groups.items():
        event_issues, components, amounts, confidences = [], [], [], []
        kinds = [kind for kind, _, _ in rows]
        status = EnergyStatus.VALID
        if key[2] == 'GD_III':
            status = EnergyStatus.UNSUPPORTED
            event_issues.append(issue('COMPENSACAO_GD_NAO_SUPORTADA', 'GD-III está fora do escopo documental atual.'))
        if len(set(kinds)) != len(kinds):
            status = EnergyStatus.AMBIGUOUS
            event_issues.append(issue('COMPENSACAO_COMPONENTE_DUPLICADO', 'Não deduplicar componentes por texto ou quantidade.'))
        elif set(kinds) != {'TE', 'TUSD'}:
            status = EnergyStatus.MISSING
            event_issues.append(issue('COMPENSACAO_COMPONENTE_AUSENTE', 'Par TE/TUSD incompleto; sem inferência.'))
        for kind, row, index in rows:
            field, unit = row.get('amount_kwh'), row.get('unit')
            source = f'itens_documentais[{index}]'
            amount = field.value if field is not None and field.status == 'found' else None
            valid = (isinstance(amount, Decimal) and amount.is_finite()
                     and unit is not None and unit.status == 'found' and unit.value == 'kWh'
                     and isinstance(field.source, str) and bool(field.source.strip()))
            if index in used_items:
                status = EnergyStatus.AMBIGUOUS
                event_issues.append(issue('COMPENSACAO_REFERENCIA_DUPLICADA', 'Uma linha não pode alimentar dois componentes/eventos.'))
            used_items.add(index)
            if not valid:
                status = EnergyStatus.AMBIGUOUS if field is not None and field.status == 'ambiguous' else (
                    status if status == EnergyStatus.AMBIGUOUS else EnergyStatus.MISSING)
                event_issues.append(issue('COMPENSACAO_QUANTIDADE_INVALIDA', 'Compensação exige quantidade documental e unidade kWh.'))
            else:
                amounts.append(amount.copy_abs())
                confidences.append(field.confidence)
            document = deepcopy(parsed.itens[index])
            components.append(ComponenteCompensacao(kind, amount if isinstance(amount, Decimal) else None,
                document.get('tarifa_unitaria'), document.get('valor'), document, source, deepcopy(row)))
        if len(set(amounts)) > 1:
            status = EnergyStatus.AMBIGUOUS
            event_issues.append(issue('DIVERGENCIA_COMPONENTES_COMPENSACAO', 'TE e TUSD possuem quantidades divergentes.'))
        quantity = amounts[0] if status == EnergyStatus.VALID else None
        confidence = min(confidences) if confidences and all(c is not None for c in confidences) else None
        events.append(CompensacaoNormalizada(*key, quantity, tuple(components),
            tuple(c.source for c in components), confidence, status, tuple(event_issues)))
        issues.extend(event_issues)

    billable = tuple(event for event in events if event.cobravel_ouc_mpt)
    if any(i.code in ('COMPENSACAO_IDENTIDADE_INDEFINIDA', 'COMPENSACAO_CATEGORIA_INDEFINIDA') for i in issues):
        status = EnergyStatus.AMBIGUOUS
    elif any(event.status == EnergyStatus.AMBIGUOUS for event in billable):
        status = EnergyStatus.AMBIGUOUS
    elif any(event.status == EnergyStatus.UNSUPPORTED for event in billable):
        status = EnergyStatus.UNSUPPORTED
    elif not billable or any(event.status == EnergyStatus.MISSING for event in billable):
        status = EnergyStatus.MISSING
    else:
        status = EnergyStatus.VALID
    if not events and not issues:
        issues.append(issue('COMPENSACAO_AUSENTE', 'Nenhuma compensação comprovada; ausência não equivale a zero.'))
    elif events and not billable:
        issues.append(issue('COMPENSACAO_OUC_MPT_AUSENTE',
                            'Nenhuma compensação OUTRA_UC/MESMO_POSTO comprovada.'))
    total = _sum_exact([event.quantidade_kwh for event in billable]) if status == EnergyStatus.VALID else None
    return BillingEnergyInput(total, tuple(events), status, tuple(issues), parsed.identity, competencia, fatura_id)
