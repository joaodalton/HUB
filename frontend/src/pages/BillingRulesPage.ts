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
import { formatDate } from '../utils/date';
import { t } from '../services/i18nService';

function methodLabels(): Record<string, string> {
  return {
    energia_compensada: t('billing.ruleEditor.methodEnergiaCompensada'),
    energia_recebida: t('billing.ruleEditor.methodEnergiaRecebida'),
    economia_gerada: t('billing.ruleEditor.methodEconomiaGerada'),
    valor_total_fatura: t('billing.ruleEditor.methodValorTotalFatura'),
    tarifa_fixa: t('billing.ruleEditor.methodTarifaFixa'),
    tarifa_fixa_com_desconto: t('billing.ruleEditor.methodTarifaFixaComDesconto'),
    tarifa_especifica: t('billing.ruleEditor.methodTarifaEspecifica')
  };
}

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

  const layout = createBaseLayout({ content, eyebrow: t('nav.section.financeiro'), title: t('nav.item.regrasCobranca') });
  void load();
  return layout;

  async function load(): Promise<void> {
    loading.show();
    try {
      [rules, assignments] = await Promise.all([listBillingRules(), listBillingRuleAssignments({ ativo: 'true' })]);
      loadError = false;
    } catch (error) {
      loadError = true;
      toast.error(error instanceof Error ? error.message : t('billing.rulesList.loadError'));
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
    const copy = createElement('p', { textContent: t('billing.rulesList.intro') });
    intro.append(copy, createContextHelp(t('billing.rulesList.defaultRuleHelpTitle'),
      t('billing.rulesList.defaultRuleHelpBody')));
    if (canWrite) {
      const add = createElement('button', { className: 'button-with-icon', type: 'button' });
      add.append(createIcon('plus'), document.createTextNode(t('billing.rulesList.newRuleButton')));
      add.addEventListener('click', () => navigate('/regras-cobranca/nova'));
      intro.appendChild(add);
      if (!company) {
        const configure = createElement('button', { className: 'secondary-button', type: 'button',
          textContent: t('billing.rulesList.configureDefaultButton') });
        configure.addEventListener('click', () => navigate('/regras-cobranca/nova?default=1'));
        intro.appendChild(configure);
      }
    }

    const filters = createElement('div', { className: 'billing-rules-filters' });
    const searchInput = createElement('input');
    searchInput.type = 'search';
    searchInput.placeholder = t('billing.rulesList.searchPlaceholder');
    searchInput.setAttribute('aria-label', t('billing.rulesList.searchAriaLabel'));
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
      filterSelect(t('billing.rulesList.filterMethodLabel'), methodFilter, [
        { value: '', label: t('billing.rulesList.filterAllMethods') },
        ...[...new Set(rules.map((rule) => rule.calculationMethod))].map((value) => ({
          value, label: methodLabels()[value] ?? value
        }))
      ], (value) => { methodFilter = value; render(); }),
      filterSelect(t('billing.rulesList.filterStatusLabel'), statusFilter, [
        { value: '', label: t('billing.rulesList.filterAllStatus') },
        { value: 'active', label: t('billing.rulesList.filterActive') },
        { value: 'inactive', label: t('billing.rulesList.filterInactive') }
      ], (value) => { statusFilter = value; render(); }));

    const table = createDataTable<RuleRow>({
      title: t('billing.rulesList.tableTitle'), eyebrow: t('billing.rulesList.tableEyebrow'), rows: visible,
      emptyMessage: loadError ? t('billing.rulesList.loadError') : t('billing.rulesList.emptyMessage'),
      columns: [
        { key: 'name', label: t('billing.rulesList.colNome'), render: ({ rule, kind }) => {
          const name = createElement('span', { className: 'billing-rule-name', textContent: rule.nome });
          if (kind === 'shared') return name;
          const cell = createElement('span', { className: 'billing-rule-name-cell' });
          cell.append(name, createElement('span', {
            className: 'status-badge tone-info', textContent: kind === 'default' ? t('billing.rulesList.badgeDefault') : t('billing.rulesList.badgeSpecific')
          }));
          return cell;
        } },
        { key: 'method', label: t('billing.rulesList.colMethod'), render: ({ rule }) => methodLabels()[rule.calculationMethod] ?? rule.calculationMethod },
        { key: 'icms', label: t('billing.rulesList.colIcmsBandeira'), render: ({ rule }) => [
          rule.billingModifiers.icmsPolicy === 'exclude' ? t('billing.ruleEditor.icmsExclude') : t('billing.ruleEditor.icmsNotConfigured'),
          rule.billingModifiers.excludeTariffFlag === true ? t('billing.ruleEditor.flagSemBandeira')
            : rule.billingModifiers.excludeTariffFlag === false ? t('billing.ruleEditor.flagComBandeira') : t('billing.rulesList.bandeiraNotConfigured')
        ].join(' · ') },
        { key: 'modifiers', label: t('billing.rulesList.colModifiers'), render: ({ rule }) => [
          rule.billingModifiers.excludePisCofins === true ? t('billing.rulesList.noPisCofins') : null,
          rule.billingModifiers.gracePeriod.enabled ? t('billing.rulesList.gracePeriodLabel') : null,
          rule.billingModifiers.recurringAdditionalCost !== null ? t('billing.rulesList.recurringSurchargeLabel') : null
        ].filter(Boolean).join(' · ') || t('billing.rulesList.noneModifiers') },
        { key: 'usage', label: t('billing.rulesList.colUcsLinked'), align: 'right', render: ({ useCount }) => String(useCount) },
        { key: 'revision', label: t('billing.rulesList.colRevision'), render: ({ rule }) => `v${rule.revision} · ${formatDate(rule.atualizadoEm)}` },
        { key: 'status', label: t('billing.rulesList.colStatus'), render: ({ rule }) => rule.ativo ? t('billing.rulesList.statusActive') : t('billing.rulesList.statusInactive') },
        { key: 'actions', label: t('billing.rulesList.colActions'), render: ({ rule, kind }) => {
          const actions = createElement('span', { className: 'billing-rule-actions' });
          const open = createElement('button', {
            className: 'secondary-button small-button', type: 'button', textContent: canWrite ? t('billing.rulesList.editButton') : t('billing.rulesList.viewButton')
          });
          open.addEventListener('click', () => navigate(`/regras-cobranca/${rule.id}/editar`));
          actions.appendChild(open);
          if (canWrite && rule.ativo && kind !== 'default') {
            const makeDefault = createElement('button', {
              className: 'secondary-button small-button', type: 'button', textContent: t('billing.rulesList.setDefaultButton')
            });
            makeDefault.addEventListener('click', () => void setDefault(rule, company));
            actions.appendChild(makeDefault);
          }
          if (canWrite && rule.ativo && !assignments.some((item) => item.grupoRegraCobrancaId === rule.id)) {
            const deactivate = createElement('button', {
              className: 'danger-button small-button', type: 'button', textContent: t('billing.rulesList.deactivateButton')
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
      textContent: t('billing.rulesList.footnote')
    }));
    content.replaceChildren(intro, filters, table);
  }

  async function setDefault(rule: BillingRule, current?: BillingRuleAssignment): Promise<void> {
    if (!window.confirm(t('billing.rulesList.confirmSetDefaultTemplate').replace('{name}', rule.nome))) return;
    loading.show();
    try {
      if (current) await updateBillingRuleAssignment(current.id, { grupoRegraCobrancaId: rule.id });
      else await createBillingRuleAssignment({ grupoRegraCobrancaId: rule.id, scopeType: 'company' });
      toast.success(t('billing.rulesList.setDefaultSuccess'));
      await load();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('billing.rulesList.setDefaultError'));
    } finally {
      loading.hide();
    }
  }

  async function deactivateRule(rule: BillingRule): Promise<void> {
    if (!window.confirm(t('billing.rulesList.confirmDeactivateTemplate').replace('{name}', rule.nome))) return;
    loading.show();
    try {
      await updateBillingRule(rule.id, { ativo: false });
      toast.success(t('billing.rulesList.deactivatedSuccess'));
      await load();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('billing.rulesList.deactivateError'));
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

function navigate(path: string): void {
  window.history.pushState({}, '', path);
  window.dispatchEvent(new PopStateEvent('popstate'));
}
