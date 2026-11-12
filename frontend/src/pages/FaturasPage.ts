import { createDataTable } from '../components/DataTable';
import { INVOICES_IMPORTED_EVENT } from '../components/InvoiceImportButton';
import { createIcon } from '../components/Icon';
import { filterSelect, createBadge, statusLabel, internoLabel, boletoBadge, currentBoleto, issuingAccess, extractionCell, kwhLabel, formatCurrency, formatDate, formatReference } from '../components/FaturasUi';
import { createElement } from '../dom';
import { useGlobalLoading } from '../hooks/useGlobalLoading';
import { useToast } from '../hooks/useToast';
import { createBaseLayout } from '../layouts/BaseLayout';
import { getCurrentUser } from '../services/authService';
import { getBillingInvoicePage, type BillingInvoice, type BillingInvoiceFilters } from '../services/billingCalculationsService';
import { getClients, type ClientRow } from '../services/clientsService';
import { getFaturas, type FaturaRow } from '../services/faturasService';
import { createFaturaInvoiceDetail } from './faturasInvoiceDetail';
import { createInvoiceActions } from './faturasInvoiceActions';
import { getPendencias, type PendenciaRow } from '../services/pendenciasService';
import { getUcs, type UcRow } from '../services/ucsService';
import { createDebouncedInput, readListParam, readPositiveListParam, writeListState } from '../services/listState';
import { t } from '../services/i18nService';

const PAGE_SIZE = 25; type InvoiceFilters = Omit<BillingInvoiceFilters, 'page' | 'pageSize'>;

export function createFaturasPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack faturas-page' });
  const toast = useToast(), loading = useGlobalLoading();
  const user = getCurrentUser();
  const { empresaId, canIssue, isPlatformAdminTestEmpresa } = issuingAccess(user);
  const canReadInvoices = Boolean(user?.isPlatformAdmin || canIssue);
  let invoices: BillingInvoice[] = [], charges: FaturaRow[] = [];
  let pendencias: PendenciaRow[] = [], clients: ClientRow[] = [], ucs: UcRow[] = [];
  let pagination = { page: 1, pageSize: PAGE_SIZE, total: 0, pages: 0 };
  let page = readPositiveListParam('pagina');
  let filters: InvoiceFilters = {
    q: readListParam('busca'), usinaId: Number(readListParam('usina')) || undefined,
    competencia: readListParam('competencia'), statusProcessamento: readListParam('processamento'),
    statusCobranca: readListParam('cobranca')
  };
  let error = false, busy = false, requestId = 0;
  const requestedInvoiceId = Number(readListParam('selecionada'));
  let selectedInvoice: BillingInvoice | null = null;
  let selectedInvoiceId: number | null = Number.isSafeInteger(requestedInvoiceId) && requestedInvoiceId > 0 ? requestedInvoiceId : null;
  let openedSelection = false;

  const layout = createBaseLayout({
    content,
    eyebrow: t('faturas.page.eyebrow'),
    title: t('faturas.page.title'),
    description: t('faturas.page.description')
  });
  const clientName = (item: BillingInvoice) => item.clienteNome ?? clients.find((client) => client.id === item.clientId)?.nome ?? t('faturas.page.noClientLink');
  const { invoiceDownloadButton, invoiceActionsCell } = createInvoiceActions({ empresaId, canIssue, toast, load, clientName });
  // O router nao desmonta paginas; popstate marca a saida da tela (mesmo padrao de PendenciasPage).
  const onImported = () => { void load(); };
  window.addEventListener(INVOICES_IMPORTED_EVENT, onImported);
  window.addEventListener('popstate', () => window.removeEventListener(INVOICES_IMPORTED_EVENT, onImported), { once: true });
  void load(); return layout;

  async function load(): Promise<void> {
    const current = ++requestId;
    busy = true; render();
    loading.show();
    try {
      if (user?.isPlatformAdmin && !empresaId) {
        invoices = []; charges = []; pendencias = []; clients = []; ucs = [];
        pagination = { page: 1, pageSize: PAGE_SIZE, total: 0, pages: 0 };
        error = false;
        return;
      }
      if (!canReadInvoices) {
        charges = await getFaturas();
        error = false;
        return;
      }
      const [invoicePage, chargeRows, pendingRows, clientRows, ucRows] = await Promise.all([
        getBillingInvoicePage({ ...filters, page, pageSize: PAGE_SIZE }, empresaId),
        user?.isPlatformAdmin && !isPlatformAdminTestEmpresa ? Promise.resolve([]) : getFaturas(),
        user?.isPlatformAdmin && !isPlatformAdminTestEmpresa ? Promise.resolve([]) : getPendencias(),
        user?.isPlatformAdmin && !isPlatformAdminTestEmpresa ? Promise.resolve([]) : getClients(),
        user?.isPlatformAdmin && !isPlatformAdminTestEmpresa ? Promise.resolve([]) : getUcs()
      ]);
      if (current !== requestId) return;
      invoices = invoicePage.data;
      if (selectedInvoiceId) selectedInvoice = invoices.find((invoice) => invoice.id === selectedInvoiceId) ?? null;
      pagination = invoicePage.pagination;
      charges = chargeRows;
      pendencias = pendingRows;
      clients = clientRows;
      ucs = ucRows;
      error = false;
    } catch (cause) {
      if (current !== requestId) return;
      error = true;
      toast.error(cause instanceof Error ? cause.message : t('faturas.page.loadError'));
    } finally {
      if (current === requestId) {
        busy = false;
        loading.hide();
        render();
        if (selectedInvoice && !openedSelection) { openedSelection = true; openInvoiceDetail(selectedInvoice, false); }
      }
    }
  }

  function applyFilters(next: InvoiceFilters): void {
    filters = next;
    page = 1;
    selectedInvoice = null;
    selectedInvoiceId = null;
    openedSelection = false;
    writeListState({ busca: filters.q, usina: filters.usinaId, competencia: filters.competencia, processamento: filters.statusProcessamento, cobranca: filters.statusCobranca, pagina: null, selecionada: null });
    void load();
  }

  function contextualCharges(invoice: BillingInvoice): FaturaRow[] {
    if (!invoice.consumerUnitId || !invoice.competencia) return [];
    return charges.filter((charge) => charge.ucId === invoice.consumerUnitId && charge.competencia === invoice.competencia);
  }

  function relatedPendencias(invoice: BillingInvoice): PendenciaRow[] {
    return pendencias.filter((item) => item.status === 'aberta' && item.faturaId === invoice.id);
  }

  function render(): void {
    content.replaceChildren(...(canReadInvoices ? [createFilters(), createTable(), createPagination()] : [createReadOnlyChargeTable()]));
  }

  function createFilters(): HTMLElement {
    const panel = createElement('section', { className: 'faturas-filter-panel' });
    const searchWrap = createElement('label', { className: 'faturas-search' });
    searchWrap.appendChild(createIcon('faturas'));
    const search = createElement('input');
    search.type = 'search';
    search.setAttribute('aria-label', t('faturas.page.searchAriaLabel'));
    search.placeholder = t('faturas.page.searchPlaceholder');
    search.value = filters.q ?? '';
    let lastAppliedQuery = filters.q ?? '';
    const applyQuery = createDebouncedInput((value) => {
      if (value === lastAppliedQuery) return;
      lastAppliedQuery = value;
      applyFilters({ ...filters, q: value || undefined });
    });
    search.addEventListener('input', () => {
      applyQuery(search.value);
    });
    searchWrap.appendChild(search);
    const plantIds = new Map<number, string>();
    ucs.flatMap((uc) => uc.conexoes).forEach((link) => plantIds.set(link.plantId, link.usina));
    const plant = filterSelect(t('faturas.page.filterUsina'), String(filters.usinaId ?? ''), [
      { value: '', label: t('faturas.page.filterUsinaAll') },
      ...[...plantIds].sort((a, b) => a[1].localeCompare(b[1])).map(([id, nome]) => ({ value: String(id), label: nome }))
    ], (value) => applyFilters({ ...filters, usinaId: value ? Number(value) : undefined }));
    const reference = createElement('label', { className: 'faturas-filter-field' });
    const referenceInput = createElement('input');
    referenceInput.type = 'month';
    referenceInput.value = filters.competencia ?? '';
    referenceInput.setAttribute('aria-label', t('faturas.page.filterCompetencia'));
    referenceInput.addEventListener('change', () => applyFilters({ ...filters, competencia: referenceInput.value }));
    reference.append(createElement('span', { textContent: t('faturas.page.filterCompetencia') }), referenceInput);
    const processing = filterSelect(t('faturas.page.filterProcessamento'), filters.statusProcessamento ?? '', [
      { value: '', label: t('faturas.page.procAll') },
      { value: 'extraida', label: t('faturas.page.procExtraida') },
      { value: 'erro', label: t('faturas.page.procErro') }
    ], (value) => applyFilters({ ...filters, statusProcessamento: value }));
    const charge = filterSelect(t('faturas.page.filterCobranca'), filters.statusCobranca ?? '', [
      { value: '', label: t('faturas.page.cobAll') }, { value: 'sem_cobranca', label: t('faturas.page.cobSem') },
      { value: 'pending', label: t('faturas.page.cobPending') }, { value: 'received', label: t('faturas.page.cobReceived') },
      { value: 'overdue', label: t('faturas.page.cobOverdue') }, { value: 'canceled', label: t('faturas.page.cobCanceled') },
      { value: 'refunded', label: t('faturas.page.cobRefunded') }
    ], (value) => applyFilters({ ...filters, statusCobranca: value }));
    panel.append(searchWrap, plant, reference, processing, charge);
    return panel;
  }

  function clientCell(item: BillingInvoice): HTMLElement {
    const cell = createElement('div', { className: 'faturas-client-cell' });
    cell.append(createElement('span', { className: item.clienteNome || item.clientId ? '' : 'faturas-problem', textContent: clientName(item) }),
      createElement('small', { textContent: item.ucCodigo ?? ucs.find((uc) => uc.id === item.consumerUnitId)?.codigo ?? '—' }));
    return cell;
  }

  function createTable(): HTMLElement {
    const hasActiveFilters = Boolean(
      filters.q || filters.usinaId || filters.competencia || filters.statusProcessamento || filters.statusCobranca
    );
    const table = createDataTable<BillingInvoice>({
      title: t('faturas.page.tableTitle'),
      eyebrow: busy ? t('faturas.page.loadingShort') : `${pagination.total} ${pagination.total === 1 ? t('faturas.page.recordSingular') : t('faturas.page.recordPlural')}`,
      rows: error || busy ? [] : invoices,
      emptyMessage: busy ? t('faturas.page.loadingInvoices') : user?.isPlatformAdmin && !empresaId ? t('faturas.page.selectCompany') : error ? t('faturas.page.loadError') : t('faturas.page.emptyDefault'),
      state: busy ? 'loading' : error ? 'error' : hasActiveFilters ? 'filtered' : 'ready',
      stateTitle: error ? t('faturas.page.stateTitleError') : hasActiveFilters ? t('faturas.page.stateTitleFiltered') : t('faturas.page.stateTitleEmpty'),
      emptyAction: { label: t('faturas.page.clearFilters'), onClick: () => applyFilters({}) },
      errorAction: { label: t('common.retry'), onClick: () => void load() },
      onRowClick: openInvoiceDetail,
      columns: [
        { key: 'competencia', label: t('faturas.page.colCompetencia'), render: (item) => formatReference(item.competencia) },
        { key: 'clienteNome', label: t('faturas.page.colClienteUc'), render: clientCell },
        { key: 'usinas', label: t('faturas.page.colUsinaShort'), render: (item) => item.usinas?.map((plant) => plant.nome).join(', ') || '—' },
        { key: 'problemas', label: t('faturas.page.colExtracao'), render: extractionCell },
        { key: 'gdIKwh', label: t('faturas.page.colGdI'), render: (item) => kwhLabel(item.gdIKwh) },
        { key: 'gdIIKwh', label: t('faturas.page.colGdII'), render: (item) => kwhLabel(item.gdIIKwh) },
        { key: 'valorTotalConcessionaria', label: t('faturas.page.colValorCopel'), align: 'right', render: (item) => formatCurrency(item.valorTotalConcessionaria) },
        { key: 'contextualCharges', label: t('faturas.page.colBoleto'), render: (item) => boletoBadge(currentBoleto(item.contextualCharges ?? []).boleto) },
        { key: 'documentoDisponivel', label: t('faturas.page.colAcoes'), render: invoiceActionsCell }
      ]
    });
    return table;
  }

  function createReadOnlyChargeTable(): HTMLElement {
    return createDataTable<FaturaRow>({
      title: t('faturas.page.readOnlyTableTitle'), eyebrow: `${charges.length} ${charges.length === 1 ? t('faturas.page.recordSingular') : t('faturas.page.recordPlural')}`,
      rows: error || busy ? [] : charges,
      emptyMessage: busy ? t('faturas.page.loadingCharges') : error ? t('faturas.page.chargesLoadError') : t('faturas.page.emptyCharges'),
      state: busy ? 'loading' : error ? 'error' : 'ready',
      stateTitle: error ? t('faturas.page.chargesStateTitleError') : t('faturas.page.chargesStateTitleEmpty'),
      columns: [
        { key: 'clienteNome', label: t('faturas.page.colCliente') },
        { key: 'ucCodigo', label: t('faturas.page.colUc') },
        { key: 'competencia', label: t('faturas.page.colCompetencia'), render: (item) => formatReference(item.competencia) },
        { key: 'valor', label: t('faturas.page.colValorComercial'), align: 'right', render: (item) => formatCurrency(item.valor) },
        { key: 'mesVencimento', label: t('faturas.page.colVencimento'), render: (item) => formatDate(item.mesVencimento) },
        { key: 'asaasStatus', label: t('faturas.page.colSituacao'), render: (item) => createBadge(item.asaasId ? statusLabel(item.asaasStatus) : item.statusInterno ? internoLabel(item.statusInterno) : t('faturas.page.awaitingIssuance')) }
      ]
    });
  }

  function createPagination(): HTMLElement {
    const nav = createElement('nav', { className: 'faturas-pagination' });
    nav.setAttribute('aria-label', t('faturas.page.paginationAriaLabel'));
    const previous = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('faturas.page.previous') });
    previous.disabled = busy || page <= 1;
    previous.addEventListener('click', () => { page--; writeListState({ pagina: page }); void load(); });
    const next = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('faturas.page.next') });
    next.disabled = busy || page >= pagination.pages;
    next.addEventListener('click', () => { page++; writeListState({ pagina: page }); void load(); });
    nav.append(previous, createElement('span', { textContent: `${pagination.pages ? page : 0} ${t('faturas.page.pageOf')} ${pagination.pages}` }), next);
    return nav;
  }

  function openInvoiceDetail(invoice: BillingInvoice, updateUrl = true): void {
    selectedInvoice = invoice;
    selectedInvoiceId = invoice.id;
    if (updateUrl) writeListState({ selecionada: invoice.id });
    createFaturaInvoiceDetail(invoice, {
      content, clients, isPlatformAdmin: Boolean(user?.isPlatformAdmin), canIssue, empresaId,
      contextualCharges, relatedPendencias, invoiceDownloadButton,
      getSelectedInvoiceId: () => selectedInvoiceId, reload: load, toast,
      onClose: () => {
        selectedInvoice = null; selectedInvoiceId = null; openedSelection = false;
        writeListState({ selecionada: null }, 'replace'); render();
      }
    });
  }
}
