// frontend/src/pages/FinanceiroPage.ts
// Fila de trabalho: clientes com fatura da concessionaria vinculada e sem boleto, por usina.
import { createDataTable } from '../components/DataTable';
import { formatCurrency, formatDate, formatReference, issuingAccess } from '../components/FaturasUi';
import { createIcon } from '../components/Icon';
import { INVOICES_IMPORTED_EVENT } from '../components/InvoiceImportButton';
import { createUiState } from '../components/UiState';
import { createElement } from '../dom';
import { useGlobalLoading } from '../hooks/useGlobalLoading';
import { useToast } from '../hooks/useToast';
import { createBaseLayout } from '../layouts/BaseLayout';
import { ApiRequestError } from '../services/apiClient';
import { getCurrentUser } from '../services/authService';
import { calculateBillingInvoice, gerarBoletoConcessionaria } from '../services/billingCalculationsService';
import { getPendentesBoleto, type PendenteBoleto, type PendentesUsina } from '../services/financeiroService';
import { t } from '../services/i18nService';
import { openBoletoPanel } from './financeiroBoletoPanel';

// Mensagem do backend; BILLING_CALCULATION_REQUIRED / INVOICE_DATA_INCOMPLETE acrescentam os detalhes.
function errorMessage(cause: unknown): string {
  if (!(cause instanceof Error) || !cause.message) return t('financeiro.page.generateError');
  if (!(cause instanceof ApiRequestError) || !cause.details || typeof cause.details !== 'object') return cause.message;
  const { stage, blockers, missing } = cause.details as { stage?: string; blockers?: string[]; missing?: string[] };
  const extra = [stage, ...(blockers ?? []), ...(missing ?? [])].filter(Boolean).join(', ');
  return extra ? `${cause.message} (${extra})` : cause.message;
}

export function createFinanceiroPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack financeiro-page' });
  const toast = useToast();
  const loading = useGlobalLoading();
  const user = getCurrentUser();
  const { empresaId, canIssue } = issuingAccess(user);
  // Admin da plataforma precisa estar dentro de uma empresa para listar.
  const needsCompany = Boolean(user?.isPlatformAdmin && !empresaId);

  let groups: PendentesUsina[] = [];
  let error = false;
  let busy = true;
  let requestId = 0;

  const layout = createBaseLayout({
    content,
    eyebrow: t('financeiro.page.eyebrow'),
    title: t('financeiro.page.title'),
    description: t('financeiro.page.description')
  });
  // O router nao desmonta paginas; popstate marca a saida da tela (mesmo padrao de PendenciasPage).
  const onImported = () => { void load(); };
  window.addEventListener(INVOICES_IMPORTED_EVENT, onImported);
  window.addEventListener('popstate', () => window.removeEventListener(INVOICES_IMPORTED_EVENT, onImported), { once: true });

  void load();
  return layout;

  async function load(): Promise<void> {
    if (needsCompany) { busy = false; render(); return; }
    const current = ++requestId;
    busy = true; render();
    loading.show();
    try {
      const result = await getPendentesBoleto();
      if (current !== requestId) return;
      groups = result; error = false;
    } catch (cause) {
      if (current !== requestId) return;
      error = true;
      toast.error(cause instanceof Error ? cause.message : t('financeiro.page.loadError'));
    } finally {
      if (current === requestId) { busy = false; loading.hide(); render(); }
    }
  }

  function render(): void {
    if (needsCompany) {
      content.replaceChildren(createUiState({ kind: 'empty', title: t('financeiro.page.selectCompany') }));
    } else if (busy || error || groups.every((group) => group.itens.length === 0)) {
      content.replaceChildren(createDataTable<PendenteBoleto>({
        title: t('financeiro.page.title'),
        eyebrow: '',
        rows: [],
        columns: [{ key: 'clienteNome', label: t('financeiro.page.colClienteUc') }],
        emptyMessage: t('financeiro.page.empty'),
        state: busy ? 'loading' : error ? 'error' : 'ready',
        stateTitle: error ? t('financeiro.page.loadError') : t('financeiro.page.empty'),
        errorAction: { label: t('common.retry'), onClick: () => void load() }
      }));
    } else {
      content.replaceChildren(...groups.filter((group) => group.itens.length).map(createGroup));
    }
  }

  function createGroup(group: PendentesUsina): HTMLElement {
    const name = group.usinaNome ?? t('financeiro.page.noPlant');
    const count = group.itens.length;
    const panel = createDataTable<PendenteBoleto>({
      title: name,
      eyebrow: count === 1 ? t('financeiro.page.waitingOne') : `${count} ${t('financeiro.page.waitingMany')}`,
      rows: group.itens,
      storageKey: 'financeiro-pendentes-boleto',
      emptyMessage: t('financeiro.page.empty'),
      columns: [
        { key: 'clienteNome', label: t('financeiro.page.colClienteUc'), render: clientCell },
        { key: 'competencia', label: t('financeiro.page.colCompetencia'), render: (item) => formatReference(item.competencia) },
        { key: 'valorConcessionaria', label: t('financeiro.page.colValorCopel'), align: 'right', render: (item) => formatCurrency(item.valorConcessionaria) },
        { key: 'valorCobrar', label: t('financeiro.page.colValorCobrar'), align: 'right', render: valueCell },
        { key: 'billingMode', label: t('financeiro.page.colTipo'), render: (item) => item.billingMode === 'unified' ? t('financeiro.page.tipoUnified') : item.billingMode === 'separate' ? t('financeiro.page.tipoSeparate') : '—' },
        { key: 'acoes', label: '', render: actionsCell }
      ]
    });
    panel.querySelector('table')?.setAttribute('aria-label', t('financeiro.page.tableLabel').replace('{usina}', name));
    return panel;
  }

  function clientCell(item: PendenteBoleto): HTMLElement {
    const cell = createElement('div', { className: 'faturas-client-cell' });
    cell.append(createElement('span', { textContent: item.clienteNome }), createElement('small', { textContent: item.ucCodigo }));
    return cell;
  }

  // emissaoPendente retoma com o valor guardado: mostra o valor mesmo havendo bloqueio.
  function isBlocked(item: PendenteBoleto): boolean {
    return Boolean(item.bloqueio) && !item.emissaoPendente;
  }

  function valueCell(item: PendenteBoleto): HTMLElement | string {
    if (!isBlocked(item)) return formatCurrency(item.valorCobrar);
    const reason = createElement('span', { className: 'faturas-problem', textContent: item.bloqueio?.message ?? '' });
    reason.id = `financeiro-bloqueio-${item.invoiceId}`;
    return reason;
  }

  function actionsCell(item: PendenteBoleto): HTMLElement {
    const cell = createElement('div', { className: 'faturas-row-actions' });
    const who = `${item.clienteNome} (${formatReference(item.competencia)})`;
    if (canIssue) cell.append(...issueButtons(item, who));

    const rule = createElement('button', { className: 'icon-button neutral', type: 'button', title: t('financeiro.page.configureRule') });
    rule.setAttribute('aria-label', `${t('financeiro.page.configureRule')} - ${who}`);
    rule.appendChild(createIcon('settings'));
    rule.addEventListener('click', () => {
      window.history.pushState({}, '', `/ucs?ucId=${item.ucId}`);
      window.dispatchEvent(new PopStateEvent('popstate'));
    });
    cell.appendChild(rule);
    return cell;
  }

  function issueButtons(item: PendenteBoleto, who: string): HTMLButtonElement[] {
    const label = item.emissaoPendente ? t('financeiro.page.resume') : t('financeiro.page.generate');
    const generate = createElement('button', { className: 'small-button', type: 'button', textContent: label });
    generate.setAttribute('aria-label', `${label} - ${who}`);
    if (isBlocked(item)) {
      generate.disabled = true;
      generate.setAttribute('aria-describedby', `financeiro-bloqueio-${item.invoiceId}`);
    }
    generate.addEventListener('click', () => {
      generate.disabled = true;
      // Segue desabilitado ate fechar o painel (a lista recarrega); reabilita so em erro.
      void generateBoleto(item).then((ok) => { if (!ok) generate.disabled = false; });
    });
    const buttons = [generate];

    if (item.bloqueio?.code === 'NOT_CALCULATED' && !item.emissaoPendente) {
      const calculate = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('financeiro.page.calculate') });
      calculate.setAttribute('aria-label', `${t('financeiro.page.calculate')} - ${who}`);
      calculate.addEventListener('click', () => {
        calculate.disabled = true;
        void calculateInvoice(item).finally(() => { calculate.disabled = false; });
      });
      buttons.push(calculate);
    }
    return buttons;
  }

  async function generateBoleto(item: PendenteBoleto): Promise<boolean> {
    try {
      const fatura = await gerarBoletoConcessionaria(item.invoiceId, empresaId);
      toast.success(t('financeiro.page.generated')
        .replace('{cliente}', item.clienteNome).replace('{valor}', formatCurrency(fatura.valor)).replace('{data}', formatDate(fatura.mesVencimento)));
      openBoletoPanel(fatura, { invoiceId: item.invoiceId, empresaId, onClose: () => { void load(); } });
      return true;
    } catch (cause) {
      toast.error(errorMessage(cause));
      return false;
    }
  }

  async function calculateInvoice(item: PendenteBoleto): Promise<void> {
    try {
      await calculateBillingInvoice(item.invoiceId, empresaId);
      toast.success(t('financeiro.page.calculated'));
      await load();
    } catch (cause) {
      toast.error(errorMessage(cause));
    }
  }
}
