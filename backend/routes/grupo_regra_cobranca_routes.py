from flask import Blueprint, request

from services import grupo_regra_cobranca_service as service
from services.grupo_regra_cobranca_service import (
    BillingRuleConflictError,
    BillingRuleValidationError,
)
from services.permission_service import require_permission
from utils.api_response import error_response, success_response


grupo_regra_cobranca_routes = Blueprint(
    'grupo_regra_cobranca_routes', __name__, url_prefix='/api/v1/billing-rules',
)


@grupo_regra_cobranca_routes.get('')
@require_permission('billing_rules.read')
def index():
    return success_response(service.list_rules())


@grupo_regra_cobranca_routes.post('')
@require_permission('billing_rules.write')
def create():
    try:
        item = service.create_rule(request.get_json(silent=True) or {})
    except BillingRuleValidationError as exc:
        return error_response(str(exc), 400, code='INVALID_BILLING_RULE')
    except BillingRuleConflictError as exc:
        return error_response(str(exc), 409, code='DEFAULT_BILLING_RULE_CONFLICT')
    return success_response(item, 'Regra de cobranca criada.', 201)


@grupo_regra_cobranca_routes.get('/<int:rule_id>')
@require_permission('billing_rules.read')
def show(rule_id: int):
    item = service.get_rule(rule_id)
    return success_response(item.to_dict()) if item else error_response('Regra de cobranca nao encontrada.', 404)


@grupo_regra_cobranca_routes.route('/<int:rule_id>', methods=['PUT', 'PATCH'])
@require_permission('billing_rules.write')
def update(rule_id: int):
    try:
        item = service.update_rule(rule_id, request.get_json(silent=True) or {})
    except BillingRuleValidationError as exc:
        return error_response(str(exc), 400, code='INVALID_BILLING_RULE')
    except BillingRuleConflictError as exc:
        return error_response(str(exc), 409, code='DEFAULT_BILLING_RULE_CONFLICT')
    return success_response(item, 'Regra de cobranca atualizada.') if item else error_response(
        'Regra de cobranca nao encontrada.', 404,
    )
