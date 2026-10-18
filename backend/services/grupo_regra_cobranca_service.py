from decimal import Decimal, InvalidOperation

from flask import g
from sqlalchemy.exc import IntegrityError

from extensions import db
from models.grupo_regra_cobranca import GrupoRegraCobranca
from models.regra_cobranca_assignment import RegraCobrancaAssignment
from services.billing_calculation_contracts import (
    BillingMode,
    CalculationMethod,
    DiscountType,
    DueDateBasis,
    TariffBasis,
    TariffSource,
    validate_commercial_method,
)


class BillingRuleValidationError(ValueError):
    pass


class BillingRuleConflictError(ValueError):
    pass


class BillingRuleInUseError(ValueError):
    pass


_FIELDS = {
    'nome': 'nome',
    'descricao': 'descricao',
    'ativo': 'ativo',
    'padrao': 'padrao',
    'calculationMethod': 'calculation_method',
    'tariffSource': 'tariff_source',
    'manualTariff': 'manual_tariff',
    'discountType': 'discount_type',
    'discountValue': 'discount_value',
    'tariffBasis': 'tariff_basis',
    'energyComponentIndex': 'energy_component_index',
    'billingMode': 'billing_mode',
    'dueDateBasis': 'due_date_basis',
    'dueDateOffsetDays': 'due_date_offset_days',
    'monthlyInterest': 'monthly_interest',
    'finePercentage': 'fine_percentage',
}
_CONFIG_FIELDS = {
    'tariffConfiguration': {
        'companyTariff': 'manual_tariff', 'tariffHfp': 'tariff_hfp', 'tariffHp': 'tariff_hp',
    },
    'billingModifiers': {
        'excludePisCofins': 'exclude_pis_cofins', 'icmsPolicy': 'icms_policy',
        'excludeTariffFlag': 'exclude_tariff_flag', 'recurringAdditionalCost': 'recurring_additional_cost',
    },
    'gracePeriod': {
        'enabled': 'grace_enabled', 'withoutDiscount': 'grace_without_discount',
        'durationMonths': 'grace_duration_months',
        'start': 'grace_start', 'end': 'grace_end',
    },
}
_NEW_COLUMNS = {column for fields in _CONFIG_FIELDS.values() for column in fields.values()} - {'manual_tariff'}
_NULLABLE_BOOLEANS = {'exclude_pis_cofins', 'exclude_tariff_flag', 'grace_enabled', 'grace_without_discount'}
_REQUIRED = {
    'nome', 'calculationMethod', 'tariffSource', 'discountType',
    'tariffBasis', 'billingMode', 'dueDateBasis', 'dueDateOffsetDays',
}
_ENUMS = {
    'calculation_method': CalculationMethod,
    'tariff_source': TariffSource,
    'discount_type': DiscountType,
    'tariff_basis': TariffBasis,
    'billing_mode': BillingMode,
    'due_date_basis': DueDateBasis,
}
_DECIMALS = {'manual_tariff', 'discount_value', 'monthly_interest', 'fine_percentage',
             'tariff_hfp', 'tariff_hp', 'recurring_additional_cost'}
_VERSIONED = {
    'calculation_method', 'tariff_source', 'manual_tariff', 'discount_type',
    'discount_value', 'tariff_basis', 'energy_component_index', 'billing_mode',
    'due_date_basis', 'due_date_offset_days', 'monthly_interest', 'fine_percentage',
}
_VERSIONED |= _NEW_COLUMNS


def list_rules() -> list[dict]:
    items = GrupoRegraCobranca.query.filter_by(
        empresa_id=g.current_empresa_id,
    ).order_by(
        GrupoRegraCobranca.ativo.desc(), GrupoRegraCobranca.padrao.desc(),
        GrupoRegraCobranca.nome, GrupoRegraCobranca.id,
    ).all()
    return [item.to_dict() for item in items]


def get_rule(rule_id: int, *, refresh: bool = False) -> GrupoRegraCobranca | None:
    query = GrupoRegraCobranca.query.filter_by(
        id=rule_id, empresa_id=g.current_empresa_id,
    )
    return (query.populate_existing() if refresh else query).first()


def create_rule(data: dict) -> dict:
    values = _validated_values(data)
    item = GrupoRegraCobranca(empresa_id=g.current_empresa_id, revision=1, **values)
    db.session.add(item)
    _commit()
    return item.to_dict()


def update_rule(rule_id: int, data: dict) -> dict | None:
    item = get_rule(rule_id)
    if not item:
        return None
    values = _validated_values(data, item)
    if item.ativo and values['ativo'] is False and RegraCobrancaAssignment.query.filter_by(
        empresa_id=g.current_empresa_id, grupo_regra_cobranca_id=item.id, ativo=True,
    ).first():
        raise BillingRuleInUseError('Regra vinculada a um assignment ativo nao pode ser desativada.')
    if any(getattr(item, field) != values[field] for field in _VERSIONED):
        item.revision += 1
    for field, value in values.items():
        setattr(item, field, value)
    _commit()
    return item.to_dict()


def set_active(rule_id: int, active: bool) -> dict | None:
    return update_rule(rule_id, {'ativo': active})


def _validated_values(data: dict, item: GrupoRegraCobranca | None = None) -> dict:
    if not isinstance(data, dict):
        raise BillingRuleValidationError('Body deve ser um objeto JSON.')
    unknown = set(data) - set(_FIELDS) - {'tariffConfiguration', 'billingModifiers'}
    if unknown:
        raise BillingRuleValidationError('Campos nao suportados: ' + ', '.join(sorted(unknown)) + '.')
    if item is None:
        missing = _REQUIRED - set(data)
        if missing:
            raise BillingRuleValidationError('Campos obrigatorios ausentes: ' + ', '.join(sorted(missing)) + '.')
        values = {**dict.fromkeys(_NEW_COLUMNS), 'ativo': True, 'padrao': False, 'descricao': None,
                  'manual_tariff': None, 'discount_value': None,
                  'energy_component_index': None, 'monthly_interest': None,
                  'fine_percentage': None}
    else:
        values = {field: getattr(item, field) for field in set(_FIELDS.values()) | _NEW_COLUMNS}

    updates = {_FIELDS[key]: value for key, value in data.items() if key in _FIELDS}
    for section in ('tariffConfiguration', 'billingModifiers'):
        if section not in data:
            continue
        payload = data[section]
        if not isinstance(payload, dict):
            raise BillingRuleValidationError(f'{section} deve ser objeto; use null nos campos para limpar.')
        allowed = set(_CONFIG_FIELDS[section]) | ({'gracePeriod'} if section == 'billingModifiers' else set())
        if set(payload) - allowed:
            raise BillingRuleValidationError(f'Campos nao suportados em {section}.')
        for key, field in _CONFIG_FIELDS[section].items():
            if key in payload:
                if field in updates and _decimal(updates[field], field) != _decimal(payload[key], key):
                    raise BillingRuleValidationError('manualTariff e companyTariff conflitantes.')
                updates[field] = payload[key]
        if 'gracePeriod' in payload:
            grace = payload['gracePeriod']
            if not isinstance(grace, dict) or set(grace) - set(_CONFIG_FIELDS['gracePeriod']):
                raise BillingRuleValidationError('gracePeriod invalido.')
            updates.update({_CONFIG_FIELDS['gracePeriod'][key]: value for key, value in grace.items()})

    for field, value in updates.items():
        api_name = next((key for key, column in _FIELDS.items() if column == field), field)
        if field in _ENUMS:
            try:
                value = _ENUMS[field](value).value
            except (TypeError, ValueError) as exc:
                raise BillingRuleValidationError(f'{api_name} invalido.') from exc
        elif field in _DECIMALS:
            value = _decimal(value, api_name)
        elif field in {'ativo', 'padrao'}:
            if type(value) is not bool:
                raise BillingRuleValidationError(f'{api_name} deve ser booleano.')
        elif field in _NULLABLE_BOOLEANS:
            if value is not None and type(value) is not bool:
                raise BillingRuleValidationError(f'{api_name} deve ser booleano ou null.')
        elif field in {'grace_start', 'grace_end'}:
            if value is not None:
                raise BillingRuleValidationError('Datas absolutas de carencia no grupo sao legadas; use durationMonths e origem do target.')
        elif field == 'grace_duration_months':
            if value is not None and (type(value) is not int or not 1 <= value <= 2147483647):
                raise BillingRuleValidationError('durationMonths deve ser inteiro positivo ou null.')
        elif field == 'due_date_offset_days':
            if type(value) is not int:
                raise BillingRuleValidationError(f'{api_name} deve ser inteiro.')
        elif field == 'energy_component_index':
            if value is not None and type(value) is not int:
                raise BillingRuleValidationError(f'{api_name} deve ser inteiro.')
        values[field] = value

    values['nome'] = str(values.get('nome') or '').strip()
    if not values['nome'] or len(values['nome']) > 150:
        raise BillingRuleValidationError('Nome deve ter entre 1 e 150 caracteres.')
    description = values.get('descricao')
    if description is not None and not isinstance(description, str):
        raise BillingRuleValidationError('Descricao deve ser texto ou null.')
    values['descricao'] = description.strip() if description else None

    if values['tariff_source'] == TariffSource.MANUAL.value:
        if values['manual_tariff'] is None:
            raise BillingRuleValidationError('manualTariff e obrigatoria para tariffSource manual.')

    if values['discount_type'] == DiscountType.NONE.value:
        if values['discount_value'] is not None:
            raise BillingRuleValidationError('discountValue deve ser null quando discountType for none.')
    elif values['discount_value'] is None:
        raise BillingRuleValidationError('discountValue e obrigatoria para desconto configurado.')

    component_index = values['energy_component_index']
    if values['tariff_basis'] == TariffBasis.DOCUMENTED_COMPONENT.value:
        if component_index is None or component_index < 0:
            raise BillingRuleValidationError('energyComponentIndex nao negativo e obrigatorio para documented_component.')
    elif component_index is not None:
        raise BillingRuleValidationError('energyComponentIndex so pode ser usado com documented_component.')

    try:
        if (values['grace_start'] is None) != (values['grace_end'] is None):
            raise ValueError('Limpe start e end legados juntos; datas existentes exigem revisao.')
        if values['grace_start'] is not None and values['grace_enabled'] is not True:
            raise ValueError('Limpe datas legadas explicitamente antes de desabilitar carencia.')
        proposed = GrupoRegraCobranca(**values)
        validate_commercial_method(values['calculation_method'], proposed.tariff_configuration,
                                   values['discount_type'], values['discount_value'])
        proposed.billing_modifiers
    except (ValueError, TypeError) as exc:
        raise BillingRuleValidationError(str(exc)) from exc
    return values


def _decimal(value, field: str) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, str) and value.strip():
        try:
            result = Decimal(value)
        except InvalidOperation as exc:
            raise BillingRuleValidationError(f'{field} deve ser Decimal textual valido.') from exc
    else:
        raise BillingRuleValidationError(f'{field} deve ser Decimal textual ou null.')
    if not result.is_finite():
        raise BillingRuleValidationError(f'{field} deve ser Decimal finito.')
    if result.copy_abs() >= Decimal('1000000000000') or result != result.quantize(Decimal('0.000001')):
        raise BillingRuleValidationError(f'{field} deve caber em Numeric(18,6) sem arredondamento.')
    return result


def _commit() -> None:
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise BillingRuleConflictError(
            'A empresa ja possui uma regra ativa marcada como padrao.'
        ) from exc
