from flask import Blueprint, request

from services import regra_cobranca_assignment_service as service
from services.permission_service import require_permission
from services.regra_cobranca_assignment_service import (
    BillingRuleAssignmentConflictError,
    BillingRuleAssignmentValidationError,
)
from utils.api_response import error_response, success_response


regra_cobranca_assignment_routes = Blueprint(
    'regra_cobranca_assignment_routes',
    __name__,
    url_prefix='/api/v1/billing-rule-assignments',
)


def _validation_error(exc):
    return error_response(str(exc), 400, code='INVALID_BILLING_RULE_ASSIGNMENT')


@regra_cobranca_assignment_routes.get('')
@require_permission('billing_rules.read')
def index():
    filters = {
        key: request.args[key] for key in (
            'scopeType', 'clientId', 'consumerUnitId', 'grupoRegraCobrancaId', 'ativo',
        ) if key in request.args
    }
    try:
        return success_response(service.list_assignments(filters))
    except BillingRuleAssignmentValidationError as exc:
        return _validation_error(exc)


@regra_cobranca_assignment_routes.post('')
@require_permission('billing_rules.write')
def create():
    try:
        item = service.create_assignment(request.get_json(silent=True) or {})
    except BillingRuleAssignmentValidationError as exc:
        return _validation_error(exc)
    except BillingRuleAssignmentConflictError as exc:
        return error_response(str(exc), 409, code='BILLING_RULE_ASSIGNMENT_CONFLICT')
    return success_response(item, 'Assignment de regra criado.', 201)


@regra_cobranca_assignment_routes.get('/<int:assignment_id>')
@require_permission('billing_rules.read')
def show(assignment_id: int):
    item = service.get_assignment(assignment_id)
    return success_response(item.to_dict()) if item else error_response(
        'Assignment de regra nao encontrado.', 404,
    )


@regra_cobranca_assignment_routes.route('/<int:assignment_id>', methods=['PUT', 'PATCH'])
@require_permission('billing_rules.write')
def update(assignment_id: int):
    try:
        item = service.update_assignment(
            assignment_id, request.get_json(silent=True) or {},
        )
    except BillingRuleAssignmentValidationError as exc:
        return _validation_error(exc)
    except BillingRuleAssignmentConflictError as exc:
        return error_response(str(exc), 409, code='BILLING_RULE_ASSIGNMENT_CONFLICT')
    return success_response(item, 'Assignment de regra atualizado.') if item else error_response(
        'Assignment de regra nao encontrado.', 404,
    )
