import { createElement } from '../dom';
import { getCurrentUser } from '../services/authService';
import {
  createBillingRuleAssignment, updateBillingRuleAssignment,
  type BillingRule, type BillingRuleAssignment
} from '../services/billingRulesService';
import type { UcRow } from '../services/ucsService';
import { useToast } from '../hooks/useToast';
import { createContextHelp } from './ContextHelp';
import { t } from '../services/i18nService';

type Options = {
  uc: UcRow;
  rules: BillingRule[];
  assignments: BillingRuleAssignment[];
  unavailable: boolean;
  onUpdated: () => Promise<void>;
};

export function createUcBillingRuleSection({ uc, rules, assignments, unavailable, onUpdated }: Options): HTMLElement {
  const toast = useToast();
  const section = createElement('section', { className: 'form-section' });
  const heading = createElement('div', { className: 'tariff-label' });
  heading.append(createElement('h3', { textContent: t('ucs.billingRule.heading') }),
    createContextHelp(t('ucs.billingRule.helpLabel'), t('ucs.billingRule.helpText')));
  section.appendChild(heading);
  if (unavailable) {
    section.appendChild(createElement('p', { textContent: t('ucs.billingRule.unavailable') }));
    return section;
  }

  const assignment = assignments.find((item) => item.scopeType === 'consumer_unit' && item.consumerUnitId === uc.id);
  const inherited = assignments.find((item) => item.scopeType === 'client' && item.clientId === uc.clienteId)
    ?? assignments.find((item) => item.scopeType === 'company');
  const selected = assignment?.grupoRegraCobrancaId ?? null;
  const canWrite = ['owner', 'admin', 'financial'].includes(getCurrentUser()?.role ?? '');
  const field = createElement('label', { className: 'form-field' });
  field.appendChild(createElement('span', { textContent: t('ucs.billingRule.fieldLabel') }));
  const select = createElement('select');
  const inheritedRule = rules.find((item) => item.id === inherited?.grupoRegraCobrancaId);
  const placeholder = createElement('option', {
    textContent: `${t('ucs.billingRule.inheritPrefix')} ${inherited?.scopeType === 'client' ? t('ucs.billingRule.inheritClient') : t('ucs.billingRule.inheritCompany')}: ${inheritedRule?.nome ?? t('ucs.billingRule.notConfigured')}`
  });
  placeholder.value = '';
  select.appendChild(placeholder);
  rules.filter((item) => item.ativo || item.id === selected).forEach((rule) => {
    const option = createElement('option', { textContent: `${rule.nome}${rule.ativo ? '' : t('ucs.billingRule.inactiveSuffix')}` });
    option.value = String(rule.id);
    option.disabled = !rule.ativo;
    select.appendChild(option);
  });
  select.value = selected ? String(selected) : '';
  select.disabled = !canWrite;
  select.addEventListener('change', async () => {
    const newRuleId = Number(select.value);
    select.disabled = true;
    try {
      if (assignment) {
        await updateBillingRuleAssignment(assignment.id, newRuleId
          ? { grupoRegraCobrancaId: newRuleId } : { ativo: false });
      } else if (newRuleId) {
        await createBillingRuleAssignment({ grupoRegraCobrancaId: newRuleId,
          scopeType: 'consumer_unit', consumerUnitId: uc.id });
      }
      toast.success(t('ucs.billingRule.toastUpdated'));
      await onUpdated();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('ucs.billingRule.toastError'));
      select.value = selected ? String(selected) : '';
      select.disabled = !canWrite;
    }
  });
  field.appendChild(select);
  section.appendChild(field);
  section.appendChild(createElement('p', {
    textContent: inherited?.scopeType === 'client'
      ? t('ucs.billingRule.hintClientFallback')
      : t('ucs.billingRule.hintCompanyFallback')
  }));

  const links = createElement('div', { className: 'form-actions' });
  const selectedRule = rules.find((item) => item.id === (selected ?? inherited?.grupoRegraCobrancaId));
  if (selectedRule) {
    const edit = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('ucs.billingRule.openRuleButton') });
    edit.addEventListener('click', () => navigateTo(`/regras-cobranca/${selectedRule.id}/editar?ucId=${uc.id}`));
    links.appendChild(edit);
  }
  if (canWrite) {
    const create = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('ucs.billingRule.createRuleButton') });
    create.addEventListener('click', () => navigateTo(`/regras-cobranca/nova?ucId=${uc.id}`));
    links.appendChild(create);
  }
  section.appendChild(links);
  return section;
}

function navigateTo(path: string): void {
  window.history.pushState({}, '', path);
  window.dispatchEvent(new PopStateEvent('popstate'));
}
