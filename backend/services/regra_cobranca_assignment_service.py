from flask import g
from sqlalchemy.exc import IntegrityError, OperationalError

from extensions import db
from models.client import Client
from models.consumer_unit import ConsumerUnit
from models.grupo_regra_cobranca import GrupoRegraCobranca
from models.regra_cobranca_assignment import RegraCobrancaAssignment
from services.billing_calculation_contracts import BillingRuleScope


class BillingRuleAssignmentValidationError(ValueError):
    pass


class BillingRuleAssignmentConflictError(ValueError):
    pass


_FIELDS = {
    'grupoRegraCobrancaId': 'grupo_regra_cobranca_id',
    'scopeType': 'scope_type',
    'clientId': 'client_id',
    'consumerUnitId': 'consumer_unit_id',
    'ativo': 'ativo',
}


def list_assignments(filters: dict | None = None) -> list[dict]:
    query = RegraCobrancaAssignment.query.filter_by(empresa_id=g.current_empresa_id)
    for field, value in _filter_values(filters or {}).items():
        query = query.filter(getattr(RegraCobrancaAssignment, field) == value)
    items = query.order_by(
        RegraCobrancaAssignment.ativo.desc(),
        RegraCobrancaAssignment.scope_type,
        RegraCobrancaAssignment.id,
    ).all()
    return [item.to_dict() for item in items]


def get_assignment(assignment_id: int, *, for_update: bool = False) -> RegraCobrancaAssignment | None:
    query = RegraCobrancaAssignment.query.filter_by(
        id=assignment_id, empresa_id=g.current_empresa_id,
    )
    return query.with_for_update().first() if for_update else query.first()


def create_assignment(data: dict) -> dict:
    values = _validated_values(data)
    item = RegraCobrancaAssignment(empresa_id=g.current_empresa_id, **values)
    db.session.add(item)
    _commit()
    return item.to_dict()


def update_assignment(assignment_id: int, data: dict) -> dict | None:
    item = get_assignment(assignment_id, for_update=True)
    if not item:
        return None
    values = _validated_values(data, item)
    changed = any(getattr(item, field) != value for field, value in values.items())
    if not changed:
        return item.to_dict()

    configuration_changed = any(
        getattr(item, field) != values[field]
        for field in ('grupo_regra_cobranca_id', 'scope_type', 'client_id', 'consumer_unit_id')
    )
    if configuration_changed and not item.ativo:
        raise BillingRuleAssignmentValidationError(
            'Assignment inativo preserva historico; crie um novo assignment.'
        )
    if configuration_changed and values['ativo'] is False:
        raise BillingRuleAssignmentValidationError(
            'Troca de regra e desativacao devem ser operacoes separadas.'
        )
    if configuration_changed:
        item.ativo = False
        db.session.flush()
        replacement = RegraCobrancaAssignment(empresa_id=g.current_empresa_id, **values)
        db.session.add(replacement)
        _commit()
        return replacement.to_dict()

    item.ativo = values['ativo']
    _commit()
    return item.to_dict()


def find_for_target(scope_type: str, *, client_id: int | None = None,
                    consumer_unit_id: int | None = None, active_only: bool = True,
                    refresh: bool = False):
    """Consulta um target exato; nao aplica precedencia nem fallback."""
    values = _validated_target(scope_type, client_id, consumer_unit_id)
    query = RegraCobrancaAssignment.query.filter_by(
        empresa_id=g.current_empresa_id, **values,
    )
    if active_only:
        query = query.filter_by(ativo=True)
    if refresh:
        query = query.populate_existing()
    return query.order_by(RegraCobrancaAssignment.id.desc()).all()


def _validated_values(data: dict, item: RegraCobrancaAssignment | None = None) -> dict:
    if not isinstance(data, dict):
        raise BillingRuleAssignmentValidationError('Body deve ser um objeto JSON.')
    unknown = set(data) - set(_FIELDS)
    if unknown:
        raise BillingRuleAssignmentValidationError(
            'Campos nao suportados: ' + ', '.join(sorted(unknown)) + '.'
        )
    if item is None:
        missing = {'grupoRegraCobrancaId', 'scopeType'} - set(data)
        if missing:
            raise BillingRuleAssignmentValidationError(
                'Campos obrigatorios ausentes: ' + ', '.join(sorted(missing)) + '.'
            )
        values = {'client_id': None, 'consumer_unit_id': None, 'ativo': True}
    else:
        values = {field: getattr(item, field) for field in _FIELDS.values()}

    for api_name, value in data.items():
        field = _FIELDS[api_name]
        if field == 'scope_type':
            try:
                value = BillingRuleScope(value).value
            except (TypeError, ValueError) as exc:
                raise BillingRuleAssignmentValidationError('scopeType invalido.') from exc
        elif field == 'ativo':
            if type(value) is not bool:
                raise BillingRuleAssignmentValidationError('ativo deve ser booleano.')
        else:
            if value is not None and (type(value) is not int or value <= 0):
                raise BillingRuleAssignmentValidationError(f'{api_name} deve ser inteiro positivo ou null.')
        values[field] = value

    values.update(_validated_target(
        values['scope_type'], values.get('client_id'), values.get('consumer_unit_id'),
    ))
    group = GrupoRegraCobranca.query.filter_by(
        id=values['grupo_regra_cobranca_id'], empresa_id=g.current_empresa_id,
    ).first()
    if not group:
        raise BillingRuleAssignmentValidationError('Grupo de regra de cobranca nao encontrado.')
    if values['ativo'] and not group.ativo:
        raise BillingRuleAssignmentValidationError(
            'Grupo de regra inativo nao pode receber assignment ativo.'
        )
    return values


def _validated_target(scope_type: str, client_id: int | None,
                      consumer_unit_id: int | None) -> dict:
    try:
        scope = BillingRuleScope(scope_type)
    except (TypeError, ValueError) as exc:
        raise BillingRuleAssignmentValidationError('scopeType invalido.') from exc

    if scope is BillingRuleScope.COMPANY:
        if client_id is not None or consumer_unit_id is not None:
            raise BillingRuleAssignmentValidationError(
                'Scope company nao aceita clientId ou consumerUnitId.'
            )
    elif scope is BillingRuleScope.CLIENT:
        if client_id is None or consumer_unit_id is not None:
            raise BillingRuleAssignmentValidationError(
                'Scope client exige clientId e nao aceita consumerUnitId.'
            )
        if not Client.query.filter_by(id=client_id, empresa_id=g.current_empresa_id).first():
            raise BillingRuleAssignmentValidationError('Client nao encontrado.')
    else:
        if consumer_unit_id is None or client_id is not None:
            raise BillingRuleAssignmentValidationError(
                'Scope consumer_unit exige consumerUnitId e nao aceita clientId.'
            )
        if not ConsumerUnit.query.filter_by(
            id=consumer_unit_id, empresa_id=g.current_empresa_id,
        ).first():
            raise BillingRuleAssignmentValidationError('ConsumerUnit nao encontrada.')
    return {
        'scope_type': scope.value,
        'client_id': client_id,
        'consumer_unit_id': consumer_unit_id,
    }


def _filter_values(filters: dict) -> dict:
    unknown = set(filters) - set(_FIELDS)
    if unknown:
        raise BillingRuleAssignmentValidationError(
            'Filtros nao suportados: ' + ', '.join(sorted(unknown)) + '.'
        )
    values = {}
    for api_name, value in filters.items():
        field = _FIELDS[api_name]
        if field == 'scope_type':
            try:
                value = BillingRuleScope(value).value
            except (TypeError, ValueError) as exc:
                raise BillingRuleAssignmentValidationError('scopeType invalido.') from exc
        elif field == 'ativo':
            normalized = str(value).lower()
            if normalized not in {'true', 'false'}:
                raise BillingRuleAssignmentValidationError('ativo deve ser true ou false.')
            value = normalized == 'true'
        else:
            try:
                value = int(value)
            except (TypeError, ValueError) as exc:
                raise BillingRuleAssignmentValidationError(f'{api_name} deve ser inteiro.') from exc
            if value <= 0:
                raise BillingRuleAssignmentValidationError(f'{api_name} deve ser inteiro positivo.')
        values[field] = value
    return values


def _commit() -> None:
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise BillingRuleAssignmentConflictError(
            'Ja existe assignment ativo para este target.'
        ) from exc
    except OperationalError as exc:
        db.session.rollback()
        if 'database is locked' in str(exc).lower():
            raise BillingRuleAssignmentConflictError(
                'Concorrencia ao configurar assignment; tente novamente.'
            ) from exc
        raise
