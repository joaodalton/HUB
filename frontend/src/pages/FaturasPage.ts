import { createDataTable } from '../components/DataTable';
import { createConcessionariaUploadButton } from '../components/ConcessionariaInvoicesPanel';
import { createIcon } from '../components/Icon';
import { createModal, detailSection, selectField, textField, option, filterSelect, createBadge, createChargeCell, statusLabel, formatCurrency, formatDate, formatReference, currentMonth } from '../components/FaturasUi';
import { createElement } from '../dom';
import { useGlobalLoading } from '../hooks/useGlobalLoading';
import { useToast } from '../hooks/useToast';
import { createBaseLayout } from '../layouts/BaseLayout';
import { getCurrentUser } from '../services/authService';
import { getBillingInvoicePage, type BillingInvoice, type BillingInvoiceFilters } from '../services/billingCalculationsService';
import { getClients, type ClientRow } from '../services/clientsService';
import { cancelFatura, createFatura, getFaturas, syncFatura, type FaturaRow } from '../services/faturasService';
import { getPendencias, type PendenciaRow } from '../services/pendenciasService';
import { getUcs, type UcRow } from '../services/ucsService';

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
  let page = 1;
  let filters: InvoiceFilters = {};
  let error = false, busy = false, requestId = 0;
  let selectedInvoice: BillingInvoice | null = null;

  const layout = createBaseLayout({ content, eyebrow: 'Financeiro', title: 'Faturas' });
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
      if (selectedInvoice) selectedInvoice = invoices.find((invoice) => invoice.id === selectedInvoice?.id) ?? null;
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
      }
    }
  }

  function applyFilters(next: InvoiceFilters): void {
    filters = next;
    page = 1;
    selectedInvoice = null;
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

  function render(): void {
    const toolbar = createElement('section', { className: 'faturas-toolbar' });
    const copy = createElement('div', { className: 'faturas-toolbar-copy' });
    copy.append(createElement('h2', { textContent: 'Faturas' }), createElement('p', { textContent: 'Documentos da concessionária e acompanhamento das cobranças comerciais.' }));
    const actions = createElement('div', { className: 'faturas-toolbar-actions' });
    const upload = createConcessionariaUploadButton(() => void load());
    if (upload) actions.appendChild(upload);
    if (canIssue) {
      const issue = createElement('button', { className: 'button-with-icon', type: 'button' });
      issue.append(createIcon('plus'), document.createTextNode('Emitir cobrança'));
      issue.disabled = !canIssueInvoice(selectedInvoice);
      issue.title = issue.disabled ? 'Selecione uma fatura validada, com UC, valor, vencimento e sem pendência operacional.' : '';
      issue.addEventListener('click', () => { if (canIssueInvoice(selectedInvoice)) openCreateModal(selectedInvoice!); });
      actions.appendChild(issue);
    }
    toolbar.append(copy, actions);
    content.replaceChildren(toolbar, ...(canReadInvoices ? [createFilters(), createTable(), createPagination()] : [createReadOnlyChargeTable()]));
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
    let timer: number | undefined;
    search.addEventListener('input', () => {
      const value = search.value;
      window.clearTimeout(timer);
      timer = window.setTimeout(() => applyFilters({ ...filters, q: value }), 300);
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
    const table = createDataTable<BillingInvoice>({
      title: 'Faturas da concessionária',
      eyebrow: busy ? 'Carregando…' : `${pagination.total} registro${pagination.total === 1 ? '' : 's'}`,
      rows: error || busy ? [] : invoices,
      emptyMessage: busy ? 'Carregando faturas…' : user?.isPlatformAdmin && !empresaId ? 'Selecione uma empresa.' : error ? 'Não foi possível carregar as faturas.' : 'Nenhuma fatura encontrada.',
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
        { key: 'temPendencia', label: 'Pendência', render: (item) => item.temPendencia ? createBadge('Aberta', 'warning') : '—' }
      ]
    });
    return table;
  }

  function createReadOnlyChargeTable(): HTMLElement {
    return createDataTable<FaturaRow>({
      title: 'Cobranças ASAAS', eyebrow: `${charges.length} registro${charges.length === 1 ? '' : 's'}`,
      rows: error || busy ? [] : charges,
      emptyMessage: busy ? 'Carregando cobranças…' : error ? 'Não foi possível carregar as cobranças.' : 'Nenhuma cobrança encontrada.',
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
    previous.addEventListener('click', () => { page--; void load(); });
    const next = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Próxima' });
    next.disabled = busy || page >= pagination.pages;
    next.addEventListener('click', () => { page++; void load(); });
    nav.append(previous, createElement('span', { textContent: `${pagination.pages ? page : 0} de ${pagination.pages}` }), next);
    return nav;
  }

  function openInvoiceDetail(invoice: BillingInvoice): void {
    selectedInvoice = invoice;
    render();
    const overlay = createModal(`Fatura da concessionária #${invoice.id}`, 'Financeiro');
    const body = overlay.querySelector('.modal-body') as HTMLElement;
    const utility = detailSection('Fatura da concessionária', [
      ['Cliente', invoice.clienteNome ?? clients.find((client) => client.id === invoice.clientId)?.nome ?? '—'],
      ['UC', invoice.ucCodigo ?? 'Aguardando validação'],
      ['Usinas vinculadas', invoice.usinas?.map((plant) => plant.nome).join(', ') || 'Sem vínculo comprovado'],
      ['Competência', formatReference(invoice.competencia)],
      ['Valor', formatCurrency(invoice.valorTotalConcessionaria)],
      ['Vencimento', formatDate(invoice.dataVencimento)],
      ['Extração', invoice.statusExtracao], ['Validação', invoice.statusValidacao]
    ]);
    const documents = createElement('section', { className: 'fatura-detail-section' });
    documents.appendChild(createElement('h3', { textContent: 'Histórico e documentos' }));
    documents.appendChild(createElement('p', { textContent: `Recebida em ${formatDate(invoice.createdAt)}.` }));
    documents.appendChild(createElement('p', { textContent: 'PDF original da concessionária: acesso não disponível nesta página.' }));
    const chargeSection = createElement('section', { className: 'fatura-detail-section' });
    chargeSection.appendChild(createElement('h3', { textContent: 'Cobrança comercial ASAAS' }));
    const linkedCharges = user?.isPlatformAdmin ? [] : contextualCharges(invoice);
    const platformCharges = user?.isPlatformAdmin ? invoice.contextualCharges ?? [] : [];
    if (!linkedCharges.length && !platformCharges.length) chargeSection.appendChild(createElement('p', { textContent: 'Nenhuma cobrança encontrada para esta UC e competência.' }));
    else {
      chargeSection.appendChild(createElement('p', { className: 'fatura-context-note', textContent: 'Cobranças encontradas pela UC e competência; o vínculo documental ainda não é confirmado pela API.' }));
      platformCharges.forEach((charge) => chargeSection.appendChild(detailSection(`Cobrança #${charge.id}`, [
        ['Valor comercial', formatCurrency(charge.valor)], ['Vencimento', formatDate(charge.mesVencimento)],
        ['Situação', charge.asaasId ? statusLabel(charge.asaasStatus as FaturaRow['asaasStatus']) : charge.statusInterno ?? 'Aguardando emissão']
      ])));
      linkedCharges.forEach((charge) => {
        const card = detailSection(`Cobrança #${charge.id}`, [
          ['Valor comercial', formatCurrency(charge.valor)], ['Vencimento', formatDate(charge.mesVencimento)],
          ['Situação', charge.asaasId ? statusLabel(charge.asaasStatus) : charge.statusInterno ?? 'Aguardando emissão']
        ]);
        const actions = createElement('div', { className: 'form-actions' });
        if (charge.boletoUrl) {
          const boleto = createElement('a', { className: 'secondary-button', textContent: 'Abrir boleto ASAAS' });
          boleto.href = charge.boletoUrl; boleto.target = '_blank'; boleto.rel = 'noreferrer'; actions.appendChild(boleto);
        }
        if (canIssue) {
          const sync = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Sincronizar' });
          sync.addEventListener('click', () => void runChargeAction(sync, () => syncFatura(charge.id), 'Cobrança sincronizada.', overlay));
          actions.appendChild(sync);
          if (charge.asaasId && charge.asaasStatus === 'pending') {
            const cancel = createElement('button', { className: 'danger-button', type: 'button', textContent: 'Cancelar cobrança' });
            cancel.addEventListener('click', () => { if (window.confirm('Cancelar esta cobrança na ASAAS?')) void runChargeAction(cancel, () => cancelFatura(charge.id), 'Cobrança cancelada.', overlay); });
            actions.appendChild(cancel);
          }
        }
        card.appendChild(actions);
        chargeSection.appendChild(card);
      });
    }
    const pendingSection = createElement('section', { className: 'fatura-detail-section' });
    pendingSection.appendChild(createElement('h3', { textContent: 'Pendências relacionadas' }));
    const related = relatedPendencias(invoice);
    if (!related.length) pendingSection.appendChild(createElement('p', { textContent: invoice.temPendencia ? 'Há pendência operacional. Consulte a central de pendências.' : 'Nenhuma pendência aberta vinculada.' }));
    related.forEach((item) => {
      const link = createElement('a', { textContent: item.titulo });
      link.href = `/pendencias?selecionada=${item.id}`;
      pendingSection.appendChild(link);
    });
    body.append(utility, chargeSection, pendingSection, documents);
    if (canIssueInvoice(invoice)) {
      const issue = createElement('button', { type: 'button', textContent: 'Emitir cobrança para esta fatura' });
      issue.addEventListener('click', () => { overlay.remove(); openCreateModal(invoice); }); body.appendChild(issue);
    }
  }

  async function runChargeAction(button: HTMLButtonElement, action: () => Promise<unknown>, message: string, overlay: HTMLElement): Promise<void> {
    button.disabled = true;
    try { await action(); toast.success(message); overlay.remove(); await load(); }
    catch (cause) { toast.error(cause instanceof Error ? cause.message : 'Não foi possível concluir a ação.'); }
    finally { button.disabled = false; }
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
