"""C3: resolve um perfil completo a partir de assignments explícitos."""
from flask import g, has_app_context

from extensions import db
from models.client import Client
from models.consumer_unit import ConsumerUnit
from services.billing_calculation_contracts import BillingRuleScope, ResolvedBillingRule
from services.grupo_regra_cobranca_service import get_rule
from services.regra_cobranca_assignment_service import (
    BillingRuleAssignmentValidationError, find_for_target,
)


class RuleResolutionError(ValueError):
    """Bloqueio de domínio; falhas técnicas do banco não são mascaradas."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


class RuleResolver:
    def resolve(self, *, client_id: int,
                consumer_unit_id: int | None = None) -> ResolvedBillingRule:
        """Usa g.current_empresa_id; chamador deve fornecer sessão de leitura limpa."""
        empresa_id = getattr(g, 'current_empresa_id', None) if has_app_context() else None
        ids = (empresa_id, client_id) + (() if consumer_unit_id is None else (consumer_unit_id,))
        if any(type(value) is not int or value <= 0 for value in ids):
            raise RuleResolutionError('invalid_context', 'Empresa e targets exigem IDs positivos no contexto.')
        if db.session.new or db.session.dirty or db.session.deleted:
            raise RuleResolutionError('invalid_context', 'Resolver exige sessão sem alterações pendentes.')

        with db.session.no_autoflush:
            if not Client.query.filter_by(id=client_id, empresa_id=empresa_id).first():
                raise RuleResolutionError('target_not_found', 'Cliente não encontrado.')
            targets = []
            if consumer_unit_id is not None:
                uc = ConsumerUnit.query.filter_by(
                    id=consumer_unit_id, empresa_id=empresa_id,
                ).populate_existing().first()
                if uc is None:
                    raise RuleResolutionError('target_not_found', 'UC não encontrada.')
                if uc.client_id != client_id:
                    raise RuleResolutionError('invalid_context', 'UC não pertence ao Cliente informado.')
                targets.append((BillingRuleScope.CONSUMER_UNIT, consumer_unit_id,
                                {'consumer_unit_id': consumer_unit_id}))
            targets.extend([
                (BillingRuleScope.CLIENT, client_id, {'client_id': client_id}),
                (BillingRuleScope.COMPANY, empresa_id, {}),
            ])
            for scope, target_id, filters in targets:
                try:
                    assignments = find_for_target(scope.value, refresh=True, **filters)
                except BillingRuleAssignmentValidationError as exc:
                    raise RuleResolutionError('target_not_found', 'Target não encontrado.') from exc
                if not assignments:
                    continue
                if len(assignments) != 1:
                    raise RuleResolutionError('assignment_inconsistent', 'Mais de um assignment ativo para o target.')
                assignment = assignments[0]
                group = get_rule(assignment.grupo_regra_cobranca_id, refresh=True)
                if group is None:
                    raise RuleResolutionError('assignment_inconsistent', 'Grupo do assignment não encontrado na empresa.')
                if not group.ativo:
                    raise RuleResolutionError('inactive_rule_assigned', 'Assignment ativo aponta para grupo inativo.')
                if group.grace_start is not None or group.grace_end is not None:
                    raise RuleResolutionError('grace_policy_migration_required',
                                              'Datas globais legadas exigem revisão da política de carência.')
                try:
                    return ResolvedBillingRule(
                        rule_id=group.id, rule_name=group.nome, rule_version=str(group.revision),
                        source_scope=scope, source_id=target_id,
                        calculation_method=group.calculation_method,
                        tariff_source=group.tariff_source, manual_tariff=group.manual_tariff,
                        discount_type=group.discount_type, discount_value=group.discount_value,
                        tariff_basis=group.tariff_basis, energy_component_index=group.energy_component_index,
                        billing_mode=group.billing_mode, due_date_basis=group.due_date_basis,
                        due_date_offset_days=group.due_date_offset_days,
                        monthly_interest=group.monthly_interest, fine_percentage=group.fine_percentage,
                        metadata={'assignment_id': str(assignment.id)},
                        tariff_configuration=group.tariff_configuration,
                        billing_modifiers=group.billing_modifiers,
                    )
                except (ValueError, TypeError) as exc:
                    raise RuleResolutionError('assignment_inconsistent', 'Grupo incompatível com o contrato financeiro.') from exc
        raise RuleResolutionError('no_rule_configured', 'Nenhum assignment ativo configurado para o contexto.')
