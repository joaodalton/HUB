import { createElement } from '../dom';
import { getCurrentUser } from '../services/authService';
import {
  createBillingRuleAssignment, updateBillingRuleAssignment,
  type BillingRule, type BillingRuleAssignment
} from '../services/billingRulesService';
import type { UcRow } from '../services/ucsService';
import { useToast } from '../hooks/useToast';
import { createContextHelp } from './ContextHelp';

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
  heading.append(createElement('h3', { textContent: 'Regra de cobrança' }),
    createContextHelp('Regra específica da UC', 'Uma regra vinculada diretamente à UC prevalece sobre as regras do cliente e da empresa. Exemplo: selecionar “Contrato especial” afeta novas execuções desta UC.'));
  section.appendChild(heading);
  if (unavailable) {
    section.appendChild(createElement('p', { textContent: 'Não foi possível carregar as regras de cobrança.' }));
    return section;
  }

  const assignment = assignments.find((item) => item.scopeType === 'consumer_unit' && item.consumerUnitId === uc.id);
  const inherited = assignments.find((item) => item.scopeType === 'client' && item.clientId === uc.clienteId)
    ?? assignments.find((item) => item.scopeType === 'company');
  const selected = assignment?.grupoRegraCobrancaId ?? null;
  const canWrite = ['owner', 'admin', 'financial'].includes(getCurrentUser()?.role ?? '');
  const field = createElement('label', { className: 'form-field' });
  field.appendChild(createElement('span', { textContent: 'Regra aplicada à UC' }));
  const select = createElement('select');
  const inheritedRule = rules.find((item) => item.id === inherited?.grupoRegraCobrancaId);
  const placeholder = createElement('option', {
    textContent: `Herdar regra do ${inherited?.scopeType === 'client' ? 'cliente' : 'empresa'}: ${inheritedRule?.nome ?? 'não configurada'}`
  });
  placeholder.value = '';
  select.appendChild(placeholder);
  rules.filter((item) => item.ativo || item.id === selected).forEach((rule) => {
    const option = createElement('option', { textContent: `${rule.nome}${rule.ativo ? '' : ' (inativa)'}` });
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
      toast.success('Vínculo da regra atualizado.');
      await onUpdated();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Não foi possível alterar a regra.');
      select.value = selected ? String(selected) : '';
      select.disabled = !canWrite;
    }
  });
  field.appendChild(select);
  section.appendChild(field);
  section.appendChild(createElement('p', {
    textContent: inherited?.scopeType === 'client'
      ? 'Sem regra direta, esta UC herda a regra do cliente antes da regra da empresa.'
      : 'Sem regra direta, esta UC utiliza o vínculo padrão da empresa, quando configurado.'
  }));

  const links = createElement('div', { className: 'form-actions' });
  const selectedRule = rules.find((item) => item.id === (selected ?? inherited?.grupoRegraCobrancaId));
  if (selectedRule) {
    const edit = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Abrir regra selecionada' });
    edit.addEventListener('click', () => navigateTo(`/regras-cobranca/${selectedRule.id}/editar?ucId=${uc.id}`));
    links.appendChild(edit);
  }
  if (canWrite) {
    const create = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Criar regra para esta UC' });
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
