import { createDataTable } from '../components/DataTable';
import { createContextHelp } from '../components/ContextHelp';
import { createIcon } from '../components/Icon';
import { createElement } from '../dom';
import { useGlobalLoading } from '../hooks/useGlobalLoading';
import { useToast } from '../hooks/useToast';
import { createBaseLayout } from '../layouts/BaseLayout';
import { getCurrentUser } from '../services/authService';
import {
  createBillingRuleAssignment,
  listBillingRuleAssignments,
  listBillingRules,
  updateBillingRule,
  updateBillingRuleAssignment,
  type BillingRule,
  type BillingRuleAssignment
} from '../services/billingRulesService';

const METHOD_LABELS: Record<string, string> = {
  energia_compensada: 'Energia compensada',
  energia_recebida: 'Energia recebida',
  economia_gerada: 'Economia gerada',
  valor_total_fatura: 'Valor total da fatura',
  tarifa_fixa: 'Tarifa fixa',
  tarifa_fixa_com_desconto: 'Tarifa fixa com desconto',
  tarifa_especifica: 'Tarifa específica'
};

type RuleRow = Record<string, unknown> & { rule: BillingRule; useCount: number; kind: 'default' | 'specific' | 'shared' };

export function createBillingRulesPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack billing-rules-page' });
  const toast = useToast();
  const loading = useGlobalLoading();
  const canWrite = ['owner', 'admin', 'financial'].includes(getCurrentUser()?.role ?? '');
  let rules: BillingRule[] = [];
  let assignments: BillingRuleAssignment[] = [];
  let search = '';
  let methodFilter = '';
  let statusFilter = '';
  let loadError = false;

  const layout = createBaseLayout({ content, eyebrow: 'Financeiro', title: 'Regras de cobrança' });
  void load();
  return layout;

  async function load(): Promise<void> {
    loading.show();
    try {
      [rules, assignments] = await Promise.all([listBillingRules(), listBillingRuleAssignments({ ativo: 'true' })]);
      loadError = false;
    } catch (error) {
      loadError = true;
      toast.error(error instanceof Error ? error.message : 'Não foi possível carregar as regras.');
    } finally {
      loading.hide();
      render();
    }
  }

  function render(): void {
    const company = assignments.find((item) => item.scopeType === 'company');
    const directUcAssignments = assignments.filter((item) => item.scopeType === 'consumer_unit');
    const rows: RuleRow[] = rules.map((rule) => ({
      rule,
      useCount: new Set(directUcAssignments.filter((item) => item.grupoRegraCobrancaId === rule.id)
        .map((item) => item.consumerUnitId)).size,
      kind: company?.grupoRegraCobrancaId === rule.id ? 'default'
        : directUcAssignments.some((item) => item.grupoRegraCobrancaId === rule.id) ? 'specific' : 'shared'
    }));
    const term = search.trim().normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
    const visible = rows.filter(({ rule }) => {
      if (methodFilter && rule.calculationMethod !== methodFilter) return false;
      if (statusFilter && (rule.ativo ? 'active' : 'inactive') !== statusFilter) return false;
      return !term || rule.nome.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().includes(term);
    });

    const intro = createElement('div', { className: 'billing-rules-intro' });
    const copy = createElement('p', { textContent: 'Configure perfis comerciais e seus vínculos. Alterações valem para novas execuções.' });
    intro.append(copy, createContextHelp('Regra padrão',
      'A regra padrão é o vínculo da empresa. UCs sem regra própria ou do cliente a usam em novas execuções. Exemplo: trocar o padrão de A para B não altera snapshots anteriores.'));
    if (canWrite) {
      const add = createElement('button', { className: 'button-with-icon', type: 'button' });
      add.append(createIcon('plus'), document.createTextNode('Nova regra'));
      add.addEventListener('click', () => navigate('/regras-cobranca/nova'));
      intro.appendChild(add);
      if (!company) {
        const configure = createElement('button', { className: 'secondary-button', type: 'button',
          textContent: 'Configurar regra padrão' });
        configure.addEventListener('click', () => navigate('/regras-cobranca/nova?default=1'));
        intro.appendChild(configure);
      }
    }

    const filters = createElement('div', { className: 'billing-rules-filters' });
    const searchInput = createElement('input');
    searchInput.type = 'search';
    searchInput.placeholder = 'Buscar por nome';
    searchInput.setAttribute('aria-label', 'Buscar regras por nome');
    searchInput.value = search;
    searchInput.addEventListener('input', () => {
      const cursor = searchInput.selectionStart ?? searchInput.value.length;
      search = searchInput.value;
      render();
      const next = content.querySelector<HTMLInputElement>('.billing-rules-filters input');
      next?.focus();
      next?.setSelectionRange(cursor, cursor);
    });
    filters.append(searchInput,
      filterSelect('Método', methodFilter, [
        { value: '', label: 'Todos os métodos' },
        ...[...new Set(rules.map((rule) => rule.calculationMethod))].map((value) => ({
          value, label: METHOD_LABELS[value] ?? value
        }))
      ], (value) => { methodFilter = value; render(); }),
      filterSelect('Status', statusFilter, [
        { value: '', label: 'Todos os status' },
        { value: 'active', label: 'Ativas' },
        { value: 'inactive', label: 'Inativas' }
      ], (value) => { statusFilter = value; render(); }));

    const table = createDataTable<RuleRow>({
      title: 'Regras cadastradas', eyebrow: 'Listagem', rows: visible,
      emptyMessage: loadError ? 'Não foi possível carregar as regras.' : 'Nenhuma regra encontrada.',
      columns: [
        { key: 'name', label: 'Nome', render: ({ rule, kind }) => {
          const name = createElement('span', { className: 'billing-rule-name', textContent: rule.nome });
          if (kind === 'shared') return name;
          const cell = createElement('span', { className: 'billing-rule-name-cell' });
          cell.append(name, createElement('span', {
            className: 'status-badge tone-info', textContent: kind === 'default' ? 'PADRÃO' : 'UC ESPECÍFICA'
          }));
          return cell;
        } },
        { key: 'method', label: 'Método tarifário', render: ({ rule }) => METHOD_LABELS[rule.calculationMethod] ?? rule.calculationMethod },
        { key: 'icms', label: 'ICMS / Bandeira', render: ({ rule }) => [
          rule.billingModifiers.icmsPolicy === 'exclude' ? 'Sem ICMS' : 'ICMS não configurado',
          rule.billingModifiers.excludeTariffFlag === true ? 'Sem bandeira'
            : rule.billingModifiers.excludeTariffFlag === false ? 'Com bandeira' : 'Bandeira não configurada'
        ].join(' · ') },
        { key: 'modifiers', label: 'Modificadores', render: ({ rule }) => [
          rule.billingModifiers.excludePisCofins === true ? 'Sem PIS/COFINS' : null,
          rule.billingModifiers.gracePeriod.enabled ? 'Carência' : null,
          rule.billingModifiers.recurringAdditionalCost !== null ? 'Adicional recorrente' : null
        ].filter(Boolean).join(' · ') || 'Nenhum' },
        { key: 'usage', label: 'UCs vinculadas', align: 'right', render: ({ useCount }) => String(useCount) },
        { key: 'revision', label: 'Revisão', render: ({ rule }) => `v${rule.revision} · ${formatDate(rule.atualizadoEm)}` },
        { key: 'status', label: 'Status', render: ({ rule }) => rule.ativo ? 'Ativa' : 'Inativa' },
        { key: 'actions', label: 'Ações', render: ({ rule, kind }) => {
          const actions = createElement('span', { className: 'billing-rule-actions' });
          const open = createElement('button', {
            className: 'secondary-button small-button', type: 'button', textContent: canWrite ? 'Editar' : 'Visualizar'
          });
          open.addEventListener('click', () => navigate(`/regras-cobranca/${rule.id}/editar`));
          actions.appendChild(open);
          if (canWrite && rule.ativo && kind !== 'default') {
            const makeDefault = createElement('button', {
              className: 'secondary-button small-button', type: 'button', textContent: 'Definir como padrão'
            });
            makeDefault.addEventListener('click', () => void setDefault(rule, company));
            actions.appendChild(makeDefault);
          }
          if (canWrite && rule.ativo && !assignments.some((item) => item.grupoRegraCobrancaId === rule.id)) {
            const deactivate = createElement('button', {
              className: 'danger-button small-button', type: 'button', textContent: 'Desativar'
            });
            deactivate.addEventListener('click', () => void deactivateRule(rule));
            actions.appendChild(deactivate);
          }
          return actions;
        } }
      ]
    });
    table.appendChild(createElement('p', {
      className: 'billing-rules-footnote',
      textContent: 'Uso conta apenas UCs com vínculo direto ativo. Vínculos herdados de cliente ou empresa não entram nessa contagem.'
    }));
    content.replaceChildren(intro, filters, table);
  }

  async function setDefault(rule: BillingRule, current?: BillingRuleAssignment): Promise<void> {
    if (!window.confirm(`Definir “${rule.nome}” como regra padrão da empresa? UCs sem regra mais específica usarão esse vínculo em novas execuções. Snapshots anteriores não mudam.`)) return;
    loading.show();
    try {
      if (current) await updateBillingRuleAssignment(current.id, { grupoRegraCobrancaId: rule.id });
      else await createBillingRuleAssignment({ grupoRegraCobrancaId: rule.id, scopeType: 'company' });
      toast.success('Regra padrão atualizada.');
      await load();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Não foi possível definir a regra padrão.');
    } finally {
      loading.hide();
    }
  }

  async function deactivateRule(rule: BillingRule): Promise<void> {
    if (!window.confirm(`Desativar “${rule.nome}”? A regra deixa de poder receber novos vínculos.`)) return;
    loading.show();
    try {
      await updateBillingRule(rule.id, { ativo: false });
      toast.success('Regra desativada.');
      await load();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Não foi possível desativar a regra.');
    } finally {
      loading.hide();
    }
  }
}

function filterSelect(label: string, value: string, options: Array<{ value: string; label: string }>, onChange: (value: string) => void): HTMLElement {
  const field = createElement('label', { className: 'form-field' });
  const select = createElement('select');
  options.forEach((option) => {
    const item = createElement('option', { textContent: option.label });
    item.value = option.value;
    select.appendChild(item);
  });
  select.value = value;
  select.addEventListener('change', () => onChange(select.value));
  field.append(createElement('span', { textContent: label }), select);
  return field;
}

function formatDate(value: string): string {
  const [year, month, day] = value.slice(0, 10).split('-');
  return year && month && day ? `${day}/${month}/${year}` : '—';
}

function navigate(path: string): void {
  window.history.pushState({}, '', path);
  window.dispatchEvent(new PopStateEvent('popstate'));
}
