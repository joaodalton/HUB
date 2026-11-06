import { createDataTable } from '../components/DataTable';
import { createConcessionariaUploadButton } from '../components/ConcessionariaInvoicesPanel';
import { createIcon } from '../components/Icon';
import { createIconStatCard } from '../components/IconStatCard';
import { createModal, selectField, textField, option, filterSelect, createBadge, createChargeCell, statusLabel, formatCurrency, formatDate, formatReference, currentMonth } from '../components/FaturasUi';
import { createElement } from '../dom';
import { attachTooltip } from '../components/Tooltip';
import { useGlobalLoading } from '../hooks/useGlobalLoading';
import { useToast } from '../hooks/useToast';
import { createBaseLayout } from '../layouts/BaseLayout';
import { getCurrentUser } from '../services/authService';
import { downloadBillingInvoice, getBillingInvoicePage, type BillingInvoice, type BillingInvoiceFilters } from '../services/billingCalculationsService';
import { getClients, type ClientRow } from '../services/clientsService';
import { createFatura, getFaturas, type FaturaRow } from '../services/faturasService';
import { createFaturaInvoiceDetail } from './faturasInvoiceDetail';
import { getPendencias, type PendenciaRow } from '../services/pendenciasService';
import { getUcs, type UcRow } from '../services/ucsService';
import { createDebouncedInput, readListParam, readPositiveListParam, writeListState } from '../services/listState';

const PAGE_SIZE = 25; type InvoiceFilters = Omit<BillingInvoiceFilters, 'page' | 'pageSize'>;

export function createFaturasPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack faturas-page' });
  const toast = useToast(), loading = useGlobalLoading();
  const user = getCurrentUser();
  const canIssue = !user?.isPlatformAdmin && ['owner', 'admin', 'financial'].includes(user?.role ?? '');
  const canReadInvoices = Boolean(user?.isPlatformAdmin || canIssue);
  const empresaId = user?.isPlatformAdmin ? user.platformViewEmpresaId ?? undefined : undefined;
  let invoices: BillingInvoice[] = [], charges: FaturaRow[] = [];
  let pendencias: PendenciaRow[] = [], clients: ClientRow[] = [], ucs: UcRow[] = [];
  let pagination = { page: 1, pageSize: PAGE_SIZE, total: 0, pages: 0 };
  let page = readPositiveListParam('pagina');
  let filters: InvoiceFilters = {
    q: readListParam('busca'), usinaId: Number(readListParam('usina')) || undefined,
    competencia: readListParam('competencia'), statusProcessamento: readListParam('processamento'),
    statusCobranca: readListParam('cobranca'),
    comPendencia: readListParam('pendencia') === 'true' ? true : readListParam('pendencia') === 'false' ? false : undefined
  };
  let error = false, busy = false, requestId = 0;
  const requestedInvoiceId = Number(readListParam('selecionada'));
  let selectedInvoice: BillingInvoice | null = null;
  let selectedInvoiceId: number | null = Number.isSafeInteger(requestedInvoiceId) && requestedInvoiceId > 0 ? requestedInvoiceId : null;
  let openedSelection = false;

  const layout = createBaseLayout({
    content,
    eyebrow: 'Financeiro',
    title: 'Faturas',
    description: 'Documentos da concessionária e acompanhamento das cobranças comerciais.'
  });
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
        user?.isPlatformAdmin ? Promise.resolve([]) : getFaturas(),
        user?.isPlatformAdmin ? Promise.resolve([]) : getPendencias(),
        user?.isPlatformAdmin ? Promise.resolve([]) : getClients(),
        user?.isPlatformAdmin ? Promise.resolve([]) : getUcs()
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
      toast.error(cause instanceof Error ? cause.message : 'Não foi possível carregar as faturas.');
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
    writeListState({ busca: filters.q, usina: filters.usinaId, competencia: filters.competencia, processamento: filters.statusProcessamento, cobranca: filters.statusCobranca, pendencia: filters.comPendencia, pagina: null, selecionada: null });
    void load();
  }

  function canIssueInvoice(invoice: BillingInvoice | null): boolean {
    return Boolean(canIssue && invoice && invoice.statusValidacao === 'valida' &&
      invoice.consumerUnitId && invoice.competencia && invoice.valorTotalConcessionaria &&
      invoice.dataVencimento && !invoice.temPendencia && !relatedPendencias(invoice).length);
  }

  function contextualCharges(invoice: BillingInvoice): FaturaRow[] {
    if (!invoice.consumerUnitId || !invoice.competencia) return [];
    return charges.filter((charge) => charge.ucId === invoice.consumerUnitId && charge.competencia === invoice.competencia);
  }

  function relatedPendencias(invoice: BillingInvoice): PendenciaRow[] {
    return pendencias.filter((item) => item.status === 'aberta' && item.faturaId === invoice.id);
  }

  function invoiceDownloadButton(invoice: BillingInvoice): HTMLButtonElement {
    const button = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Baixar PDF' });
    button.addEventListener('click', (event) => {
      event.stopPropagation();
      button.disabled = true;
      void downloadBillingInvoice(invoice.id, empresaId).catch((cause) => {
        toast.error(cause instanceof Error ? cause.message : 'Não foi possível baixar a fatura.');
      }).finally(() => { button.disabled = false; });
    });
    button.addEventListener('keydown', (event) => event.stopPropagation());
    return button;
  }

  function render(): void {
    const toolbar = createElement('section', { className: 'faturas-toolbar' });
    const actions = createElement('div', { className: 'faturas-toolbar-actions' });
    const upload = createConcessionariaUploadButton(() => void load());
    if (upload) actions.appendChild(upload);
    if (canIssue) {
      const issue = createElement('button', { className: 'button-with-icon', type: 'button' });
      issue.append(createIcon('plus'), document.createTextNode('Emitir cobrança'));
      issue.disabled = !canIssueInvoice(selectedInvoice);
      issue.title = issue.disabled ? 'Selecione uma fatura validada, com UC, valor, vencimento e sem pendência operacional.' : '';
      if (issue.disabled) attachTooltip(issue, issue.title);
      issue.addEventListener('click', () => { if (canIssueInvoice(selectedInvoice)) openCreateModal(selectedInvoice!); });
      actions.appendChild(issue);
    }
    toolbar.append(actions);
    content.replaceChildren(toolbar, ...(canReadInvoices
      ? [createFilters(), createSummary(), createTable(), createPagination()]
      : [createSummary(), createReadOnlyChargeTable()]));
  }

  function createSummary(): HTMLElement {
    const grid = createElement('section', { className: 'metric-grid' });
    const rows = canReadInvoices
      ? [
          { label: 'Faturas', value: String(pagination.total), chipColor: 'blue' as const, icon: 'faturas' as const },
          { label: 'Com pendência', value: String(invoices.filter((item) => item.temPendencia).length), chipColor: 'amber' as const, icon: 'pending' as const },
          { label: 'Cobranças', value: String(charges.length), chipColor: 'green' as const, icon: 'cobrancas' as const }
        ]
      : [{ label: 'Cobranças', value: String(charges.length), chipColor: 'green' as const, icon: 'cobrancas' as const }];
    rows.forEach((item) => grid.appendChild(createIconStatCard(item)));
    return grid;
  }

  function createFilters(): HTMLElement {
    const panel = createElement('section', { className: 'faturas-filter-panel' });
    const searchWrap = createElement('label', { className: 'faturas-search' });
    searchWrap.appendChild(createIcon('faturas'));
    const search = createElement('input');
    search.type = 'search';
    search.setAttribute('aria-label', 'Buscar por cliente ou UC');
    search.placeholder = 'Cliente ou UC';
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
    const plant = filterSelect('Usina', String(filters.usinaId ?? ''), [
      { value: '', label: 'Todas as usinas' },
      ...[...plantIds].sort((a, b) => a[1].localeCompare(b[1])).map(([id, nome]) => ({ value: String(id), label: nome }))
    ], (value) => applyFilters({ ...filters, usinaId: value ? Number(value) : undefined }));
    const reference = createElement('label', { className: 'faturas-filter-field' });
    const referenceInput = createElement('input');
    referenceInput.type = 'month';
    referenceInput.value = filters.competencia ?? '';
    referenceInput.setAttribute('aria-label', 'Competência');
    referenceInput.addEventListener('change', () => applyFilters({ ...filters, competencia: referenceInput.value }));
    reference.append(createElement('span', { textContent: 'Competência' }), referenceInput);
    const processing = filterSelect('Processamento', filters.statusProcessamento ?? '', [
      { value: '', label: 'Todos' },
      { value: 'recebida', label: 'Recebida' },
      { value: 'extraida', label: 'Extraída' },
      { value: 'valida', label: 'Validada' },
      { value: 'erro', label: 'Erro' }
    ], (value) => applyFilters({ ...filters, statusProcessamento: value }));
    const charge = filterSelect('Cobrança', filters.statusCobranca ?? '', [
      { value: '', label: 'Todas' }, { value: 'sem_cobranca', label: 'Sem cobrança' },
      { value: 'pending', label: 'Pendente' }, { value: 'received', label: 'Recebida' },
      { value: 'overdue', label: 'Vencida' }, { value: 'canceled', label: 'Cancelada' },
      { value: 'refunded', label: 'Estornada' }
    ], (value) => applyFilters({ ...filters, statusCobranca: value }));
    const pending = filterSelect('Pendência', filters.comPendencia === undefined ? '' : String(filters.comPendencia), [
      { value: '', label: 'Todas' }, { value: 'true', label: 'Com pendência' }, { value: 'false', label: 'Sem pendência' }
    ], (value) => applyFilters({ ...filters, comPendencia: value ? value === 'true' : undefined }));
    panel.append(searchWrap, plant, reference, processing, charge, pending);
    return panel;
  }

  function createTable(): HTMLElement {
    const hasActiveFilters = Boolean(
      filters.q || filters.usinaId || filters.competencia || filters.statusProcessamento || filters.statusCobranca || filters.comPendencia !== undefined
    );
    const table = createDataTable<BillingInvoice>({
      title: 'Faturas da concessionária',
      eyebrow: busy ? 'Carregando…' : `${pagination.total} registro${pagination.total === 1 ? '' : 's'}`,
      rows: error || busy ? [] : invoices,
      emptyMessage: busy ? 'Carregando faturas…' : user?.isPlatformAdmin && !empresaId ? 'Selecione uma empresa.' : error ? 'Não foi possível carregar as faturas.' : 'Nenhuma fatura encontrada.',
      state: busy ? 'loading' : error ? 'error' : hasActiveFilters ? 'filtered' : 'ready',
      stateTitle: error ? 'Nao foi possivel carregar as faturas' : hasActiveFilters ? 'Nenhuma fatura corresponde aos filtros' : 'Nenhuma fatura encontrada',
      emptyAction: { label: 'Limpar filtros', onClick: () => applyFilters({}) },
      errorAction: { label: 'Tentar novamente', onClick: () => void load() },
      onRowClick: openInvoiceDetail,
      columns: [
        { key: 'usinas', label: 'Usina / contexto', render: (item) => item.usinas?.map((plant) => plant.nome).join(', ') || 'Sem vínculo de usina' },
        { key: 'clienteNome', label: 'Cliente', render: (item) => item.clienteNome ?? clients.find((client) => client.id === item.clientId)?.nome ?? '—' },
        { key: 'ucCodigo', label: 'UC', render: (item) => item.ucCodigo ?? ucs.find((uc) => uc.id === item.consumerUnitId)?.codigo ?? 'Aguardando validação' },
        { key: 'competencia', label: 'Competência', render: (item) => formatReference(item.competencia) },
        { key: 'valorTotalConcessionaria', label: 'Valor da concessionária', align: 'right', render: (item) => formatCurrency(item.valorTotalConcessionaria) },
        { key: 'dataVencimento', label: 'Vencimento', render: (item) => formatDate(item.dataVencimento) },
        { key: 'statusProcessamento', label: 'Processamento', render: (item) => createBadge(item.statusValidacao === 'pendente' ? item.statusExtracao : item.statusValidacao) },
        { key: 'statusCobranca', label: 'Cobrança', render: (item) => createChargeCell(item.contextualCharges ?? contextualCharges(item)) },
        { key: 'temPendencia', label: 'Pendência', render: (item) => item.temPendencia ? createBadge('Aberta', 'warning') : '—' },
        { key: 'documentoDisponivel', label: 'PDF', render: (item) => item.documentoDisponivel ? invoiceDownloadButton(item) : '—' }
      ]
    });
    return table;
  }

  function createReadOnlyChargeTable(): HTMLElement {
    return createDataTable<FaturaRow>({
      title: 'Cobranças ASAAS', eyebrow: `${charges.length} registro${charges.length === 1 ? '' : 's'}`,
      rows: error || busy ? [] : charges,
      emptyMessage: busy ? 'Carregando cobranças…' : error ? 'Não foi possível carregar as cobranças.' : 'Nenhuma cobrança encontrada.',
      state: busy ? 'loading' : error ? 'error' : 'ready',
      stateTitle: error ? 'Nao foi possivel carregar as cobrancas' : 'Nenhuma cobranca encontrada',
      columns: [
        { key: 'clienteNome', label: 'Cliente' },
        { key: 'ucCodigo', label: 'UC' },
        { key: 'competencia', label: 'Competência', render: (item) => formatReference(item.competencia) },
        { key: 'valor', label: 'Valor comercial', align: 'right', render: (item) => formatCurrency(item.valor) },
        { key: 'mesVencimento', label: 'Vencimento', render: (item) => formatDate(item.mesVencimento) },
        { key: 'asaasStatus', label: 'Situação', render: (item) => createBadge(item.asaasId ? statusLabel(item.asaasStatus) : item.statusInterno ?? 'Aguardando emissão') }
      ]
    });
  }

  function createPagination(): HTMLElement {
    const nav = createElement('nav', { className: 'faturas-pagination' });
    nav.setAttribute('aria-label', 'Páginas de faturas');
    const previous = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Anterior' });
    previous.disabled = busy || page <= 1;
    previous.addEventListener('click', () => { page--; writeListState({ pagina: page }); void load(); });
    const next = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Próxima' });
    next.disabled = busy || page >= pagination.pages;
    next.addEventListener('click', () => { page++; writeListState({ pagina: page }); void load(); });
    nav.append(previous, createElement('span', { textContent: `${pagination.pages ? page : 0} de ${pagination.pages}` }), next);
    return nav;
  }

  function openInvoiceDetail(invoice: BillingInvoice, updateUrl = true): void {
    selectedInvoice = invoice;
    selectedInvoiceId = invoice.id;
    if (updateUrl) writeListState({ selecionada: invoice.id });
    createFaturaInvoiceDetail(invoice, {
      content, clients, isPlatformAdmin: Boolean(user?.isPlatformAdmin), canIssue, empresaId,
      contextualCharges, relatedPendencias, invoiceDownloadButton, canIssueInvoice, openCreateModal,
      getSelectedInvoiceId: () => selectedInvoiceId, reload: load, toast,
      onClose: () => {
        selectedInvoice = null; selectedInvoiceId = null; openedSelection = false;
        writeListState({ selecionada: null }, 'replace'); render();
      }
    });
  }

  function openCreateModal(invoice: BillingInvoice): void {
    const overlay = createModal('Emitir cobrança', 'Financeiro');
    const form = createElement('form', { className: 'client-form' });
    const client = selectField('Cliente', clients.map((item) => ({ value: String(item.id), label: item.nome })), true);
    const uc = selectField('UC', [], true);
    const concessionaria = textField('Concessionária', 'text', '', true);
    concessionaria.input.readOnly = true;
    const competencia = textField('Competência', 'month', currentMonth(), true);
    const vencimento = textField('Vencimento da cobrança', 'date', '', true);
    const valor = textField('Valor comercial (R$)', 'number', '', true);
    valor.input.min = '0.01'; valor.input.step = '0.01';
    const notice = createElement('p', { className: 'fatura-notice', textContent: 'A cobrança será emitida na ASAAS. Informe o valor comercial final; o valor da concessionária é um documento distinto.' });
    const actions = createElement('div', { className: 'form-actions' });
    const submit = createElement('button', { type: 'submit', textContent: 'Emitir cobrança' });
    const cancel = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Cancelar' });
    cancel.addEventListener('click', () => overlay.remove());
    actions.append(submit, cancel);
    function refreshUcs(): void {
      const selectedClientId = Number(client.select.value);
      const options = ucs.filter((item) => item.clienteId === selectedClientId);
      uc.select.replaceChildren(...options.map((item) => option(String(item.id), item.codigo)));
      concessionaria.input.value = options[0]?.concessionaria ?? '';
    }
    client.select.addEventListener('change', refreshUcs);
    uc.select.addEventListener('change', () => { concessionaria.input.value = ucs.find((item) => item.id === Number(uc.select.value))?.concessionaria ?? ''; });
    refreshUcs();
    client.select.value = String(invoice.clientId);
    refreshUcs();
    uc.select.value = String(invoice.consumerUnitId);
    concessionaria.input.value = ucs.find((item) => item.id === invoice.consumerUnitId)?.concessionaria ?? '';
    competencia.input.value = invoice.competencia ?? '';
    client.select.disabled = true;
    uc.select.disabled = true;
    competencia.input.readOnly = true;
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (!form.reportValidity() || !canIssueInvoice(invoice)) return;
      submit.disabled = true;
      try {
        await createFatura({ clienteId: Number(client.select.value), ucId: Number(uc.select.value), valor: Number(valor.input.value), competencia: competencia.input.value, mesVencimento: vencimento.input.value });
        toast.success('Cobrança emitida.'); overlay.remove(); await load();
      } catch (cause) { toast.error(cause instanceof Error ? cause.message : 'Não foi possível emitir a cobrança.'); }
      finally { submit.disabled = false; }
    });
    const grid = createElement('div', { className: 'form-grid' });
    client.field.classList.add('form-field-wide');
    grid.append(client.field, uc.field, concessionaria.field, competencia.field, vencimento.field, valor.field);
    form.append(grid, notice, actions);
    overlay.querySelector('.modal-body')?.appendChild(form);
  }
}
