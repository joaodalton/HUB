import { createDashboardCards, type DashboardMetric } from '../components/DashboardCards';
import { createDataTable } from '../components/DataTable';
import { createIcon } from '../components/Icon';
import { createElement } from '../dom';
import { useGlobalLoading } from '../hooks/useGlobalLoading';
import { useToast } from '../hooks/useToast';
import { createBaseLayout } from '../layouts/BaseLayout';
import { getClients, type ClientRow } from '../services/clientsService';
import { cancelFatura, createFatura, getFaturas, getFaturasResumo, syncFatura, type FaturaRow, type FaturaStatus, type FaturasResumo } from '../services/faturasService';
import { getUcs, type UcRow } from '../services/ucsService';

const STATUS: Array<{ value: FaturaStatus; label: string; tone: DashboardMetric['tone'] }> = [
  { value: 'pending', label: 'Pendentes', tone: 'warning' },
  { value: 'received', label: 'Recebidas', tone: 'success' },
  { value: 'overdue', label: 'Vencidas', tone: 'danger' },
  { value: 'canceled', label: 'Canceladas', tone: 'neutral' }
];

export function createFaturasPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack faturas-page' });
  const toast = useToast();
  const loading = useGlobalLoading();
  let faturas: FaturaRow[] = [];
  let resumo: FaturasResumo = {};
  let clients: ClientRow[] = [];
  let ucs: UcRow[] = [];
  let searchTerm = '';
  let statusFilter: FaturaStatus | undefined;
  let referenceFilter = '';
  let clientFilter = '';
  let ucFilter = '';
  const selectedIds = new Set<number>();

  const layout = createBaseLayout({ content, eyebrow: 'Financeiro', title: 'Faturas' });
  void load();
  return layout;

  async function load(): Promise<void> {
    loading.show();
    try {
      [faturas, resumo, clients, ucs] = await Promise.all([getFaturas(), getFaturasResumo(), getClients(), getUcs()]);
      const availableIds = new Set(faturas.map((fatura) => fatura.id));
      selectedIds.forEach((id) => { if (!availableIds.has(id)) selectedIds.delete(id); });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Não foi possível carregar as faturas.');
    } finally {
      loading.hide();
      render();
    }
  }

  function filtered(): FaturaRow[] {
    const term = normalize(searchTerm);
    return faturas.filter((fatura) => {
      if (statusFilter && fatura.asaasStatus !== statusFilter) return false;
      if (referenceFilter && fatura.competencia !== referenceFilter) return false;
      if (clientFilter && fatura.clienteId !== Number(clientFilter)) return false;
      if (ucFilter && fatura.ucId !== Number(ucFilter)) return false;
      return !term || normalize(`${fatura.externalReference ?? ''} ${fatura.clienteNome} ${fatura.ucCodigo} ${fatura.competencia}`).includes(term);
    });
  }

  function render(): void {
    const toolbar = createElement('section', { className: 'faturas-toolbar' });
    const toolbarText = createElement('div', { className: 'faturas-toolbar-copy' });
    toolbarText.append(
      createElement('span', { className: 'eyebrow', textContent: 'Gestão financeira' }),
      createElement('h2', { textContent: 'Visão geral das faturas' }),
      createElement('p', { textContent: 'Acompanhe referências, clientes, unidades consumidoras e status de cobrança.' })
    );
    const toolbarActions = createElement('div', { className: 'faturas-toolbar-actions' });
    const add = createElement('button', { className: 'button-with-icon', type: 'button' });
    add.append(createIcon('plus'), document.createTextNode('Nova fatura'));
    add.addEventListener('click', openCreateModal);
    toolbarActions.appendChild(add);
    toolbar.append(toolbarText, toolbarActions);

    content.replaceChildren(toolbar, createCards(), createFilters(), createTable());
  }

  function createFilters(): HTMLElement {
    const panel = createElement('section', { className: 'faturas-filter-panel' });
    const searchWrap = createElement('label', { className: 'faturas-search' });
    searchWrap.appendChild(createIcon('faturas'));
    const search = createElement('input');
    search.type = 'search';
    search.setAttribute('aria-label', 'Buscar faturas');
    search.placeholder = 'Buscar por referência, UC ou cliente';
    search.value = searchTerm;
    search.addEventListener('input', () => {
      const cursor = search.selectionStart ?? search.value.length;
      searchTerm = search.value;
      render();
      const next = content.querySelector<HTMLInputElement>('.faturas-search input');
      next?.focus();
      next?.setSelectionRange(cursor, cursor);
    });
    searchWrap.appendChild(search);

    const references = [...new Set(faturas.map((fatura) => fatura.competencia))]
      .sort((a, b) => b.localeCompare(a));
    const reference = filterSelect('Referência', referenceFilter, [
      { value: '', label: 'Todas as referências' },
      ...references.map((value) => ({ value, label: formatReference(value) }))
    ], (value) => { referenceFilter = value; render(); });
    const status = filterSelect('Status', statusFilter ?? '', [
      { value: '', label: 'Todos os status' },
      ...STATUS.map(({ value, label }) => ({ value, label }))
    ], (value) => { statusFilter = (value || undefined) as FaturaStatus | undefined; render(); });
    const client = filterSelect('Cliente', clientFilter, [
      { value: '', label: 'Todos os clientes' },
      ...clients.map((item) => ({ value: String(item.id), label: item.nome }))
    ], (value) => { clientFilter = value; ucFilter = ''; render(); });
    const availableUcs = clientFilter
      ? ucs.filter((item) => item.clienteId === Number(clientFilter))
      : ucs;
    const uc = filterSelect('UC', ucFilter, [
      { value: '', label: 'Todas as UCs' },
      ...availableUcs.map((item) => ({ value: String(item.id), label: item.codigo }))
    ], (value) => { ucFilter = value; render(); });
    const clear = createElement('button', {
      className: 'secondary-button faturas-clear-filters', type: 'button', textContent: 'Limpar filtros'
    });
    clear.disabled = !searchTerm && !statusFilter && !referenceFilter && !clientFilter && !ucFilter;
    clear.addEventListener('click', () => {
      searchTerm = ''; statusFilter = undefined; referenceFilter = ''; clientFilter = ''; ucFilter = ''; render();
    });
    panel.append(searchWrap, reference, status, client, uc, clear);
    return panel;
  }

  function createCards(): HTMLElement {
    const totalValue = faturas.reduce((sum, fatura) => sum + Number(fatura.valor || 0), 0);
    const metrics: DashboardMetric[] = [{
      label: 'Total de faturas', value: String(faturas.length), tone: 'neutral',
      active: !statusFilter,
      onClick: () => { statusFilter = undefined; render(); }
    }, ...STATUS.map(({ value, label, tone }) => ({
      label,
      value: String(resumo[value] ?? faturas.filter((fatura) => fatura.asaasStatus === value).length),
      tone,
      active: statusFilter === value,
      onClick: () => { statusFilter = statusFilter === value ? undefined : value; render(); }
    })), {
      label: 'Valor total', value: formatCurrency(totalValue), tone: 'neutral'
    }];
    const cards = createDashboardCards(metrics);
    cards.classList.add('faturas-metrics');
    return cards;
  }

  function createTable(): HTMLElement {
    const rows = filtered();
    const visibleIds = rows.map((fatura) => fatura.id);
    const selectedVisible = visibleIds.filter((id) => selectedIds.has(id)).length;
    return createDataTable<FaturaRow>({
      title: selectedIds.size ? `Lista de faturas · ${selectedIds.size} selecionada${selectedIds.size === 1 ? '' : 's'}` : 'Lista de faturas',
      eyebrow: `${rows.length} registro${rows.length === 1 ? '' : 's'}`, rows,
      emptyMessage: 'Nenhuma fatura encontrada.', onRowClick: openDetailModal,
      columns: [
        {
          key: 'selecao', label: 'Selecionar',
          headerRender: () => createSelectAllCheckbox(visibleIds, selectedVisible),
          render: (fatura) => createRowCheckbox(fatura)
        },
        { key: 'competencia', label: 'Referência', render: (fatura) => formatReference(fatura.competencia) },
        { key: 'ucCodigo', label: 'UC', render: (fatura) => createUcCell(fatura) },
        { key: 'clienteNome', label: 'Cliente' },
        { key: 'mesVencimento', label: 'Vencimento', render: (fatura) => formatDate(fatura.mesVencimento) },
        { key: 'valor', label: 'Valor', align: 'right', render: (fatura) => formatCurrency(fatura.valor) },
        { key: 'asaasStatus', label: 'Status', render: (fatura) => createStatusBadge(fatura.asaasStatus) },
        { key: 'acoes', label: 'Ação', align: 'right', render: (fatura) => createActions(fatura) }
      ]
    });
  }

  function createSelectAllCheckbox(visibleIds: number[], selectedVisible: number): HTMLElement {
    const input = selectionCheckbox('Selecionar todas as faturas visíveis');
    input.checked = visibleIds.length > 0 && selectedVisible === visibleIds.length;
    input.indeterminate = selectedVisible > 0 && selectedVisible < visibleIds.length;
    input.disabled = visibleIds.length === 0;
    input.addEventListener('change', () => {
      visibleIds.forEach((id) => input.checked ? selectedIds.add(id) : selectedIds.delete(id));
      render();
    });
    return input;
  }

  function createRowCheckbox(fatura: FaturaRow): HTMLElement {
    const input = selectionCheckbox(`Selecionar fatura de ${fatura.clienteNome}, referência ${formatReference(fatura.competencia)}`);
    input.checked = selectedIds.has(fatura.id);
    input.addEventListener('change', () => {
      if (input.checked) selectedIds.add(fatura.id);
      else selectedIds.delete(fatura.id);
      render();
    });
    return input;
  }

  function createActions(fatura: FaturaRow): HTMLElement {
    const wrap = createElement('div', { className: 'table-actions' });
    const button = createElement('button', { className: 'icon-button neutral', type: 'button', title: 'Ver fatura' });
    button.appendChild(createIcon('eye'));
    button.addEventListener('click', (event) => { event.stopPropagation(); openDetailModal(fatura); });
    wrap.appendChild(button);
    return wrap;
  }

  function openCreateModal(): void {
    const overlay = createModal('Nova fatura', 'Financeiro');
    const form = createElement('form', { className: 'client-form' });
    const client = selectField('Cliente', clients.map((item) => ({ value: String(item.id), label: item.nome })), true);
    const uc = selectField('UC', [], true);
    const concessionaria = textField('Concessionária', 'text', '', true);
    concessionaria.input.readOnly = true;
    const competencia = textField('Competência', 'month', currentMonth(), true);
    const vencimento = textField('Vencimento', 'date', '', true);
    const valor = textField('Valor (R$)', 'number', '', true);
    valor.input.min = '0.01'; valor.input.step = '0.01';
    const notice = createElement('p', { className: 'fatura-notice', textContent: 'Ao confirmar, a cobrança será emitida na ASAAS. Para corrigir, cancele e emita uma nova fatura.' });
    const actions = createElement('div', { className: 'form-actions' });
    const submit = createElement('button', { type: 'submit', textContent: 'Emitir fatura' });
    const cancel = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Cancelar' });
    cancel.addEventListener('click', () => overlay.remove());
    actions.append(submit, cancel);

    function refreshUcs(): void {
      const selectedClientId = Number(client.select.value);
      const options = ucs.filter((item) => item.clienteId === selectedClientId);
      uc.select.replaceChildren(...options.map((item) => option(String(item.id), item.codigo)));
      const selected = options[0];
      concessionaria.input.value = selected?.concessionaria ?? '';
    }
    client.select.addEventListener('change', refreshUcs);
    uc.select.addEventListener('change', () => { concessionaria.input.value = ucs.find((item) => item.id === Number(uc.select.value))?.concessionaria ?? ''; });
    refreshUcs();

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (!form.reportValidity()) return;
      submit.disabled = true;
      try {
        await createFatura({ clienteId: Number(client.select.value), ucId: Number(uc.select.value), valor: Number(valor.input.value), competencia: competencia.input.value, mesVencimento: vencimento.input.value });
        toast.success('Fatura emitida.');
        overlay.remove();
        await load();
      } catch (error) {
        toast.error(error instanceof Error ? error.message : 'Não foi possível emitir a fatura.');
      } finally { submit.disabled = false; }
    });
    const grid = createElement('div', { className: 'form-grid' });
    client.field.classList.add('form-field-wide');
    grid.append(client.field, uc.field, concessionaria.field, competencia.field, vencimento.field, valor.field);
    form.append(grid, notice, actions);
    overlay.querySelector('.modal-body')?.appendChild(form);
  }

  function openDetailModal(fatura: FaturaRow): void {
    const overlay = createModal(`Fatura #${fatura.id}`, 'Financeiro');
    const body = overlay.querySelector('.modal-body') as HTMLElement;
    const info = createElement('div', { className: 'detail-info-grid' });
    [['Cliente', fatura.clienteNome], ['UC', fatura.ucCodigo], ['Competência', fatura.competencia], ['Valor', formatCurrency(fatura.valor)], ['Vencimento', formatDate(fatura.mesVencimento)], ['Status', statusLabel(fatura.asaasStatus)]].forEach(([label, value]) => {
      const field = createElement('div', { className: 'detail-info-field' });
      field.append(createElement('span', { textContent: label }), createElement('strong', { textContent: value }));
      info.appendChild(field);
    });
    const actions = createElement('div', { className: 'form-actions' });
    if (fatura.boletoUrl) {
      const boleto = createElement('a', { className: 'secondary-button', textContent: 'Abrir boleto' });
      boleto.href = fatura.boletoUrl; boleto.target = '_blank'; boleto.rel = 'noreferrer'; actions.appendChild(boleto);
    }
    const sync = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Sincronizar' });
    sync.addEventListener('click', () => void runAction(sync, () => syncFatura(fatura.id), 'Fatura sincronizada.'));
    actions.appendChild(sync);
    if (fatura.asaasStatus === 'pending') {
      const cancel = createElement('button', { className: 'danger-button', type: 'button', textContent: 'Cancelar fatura' });
      cancel.addEventListener('click', () => { if (window.confirm('Cancelar esta fatura na ASAAS?')) void runAction(cancel, () => cancelFatura(fatura.id), 'Fatura cancelada.'); });
      actions.appendChild(cancel);
    }
    body.append(info, actions);
    async function runAction(button: HTMLButtonElement, action: () => Promise<unknown>, message: string): Promise<void> {
      button.disabled = true;
      try { await action(); toast.success(message); overlay.remove(); await load(); }
      catch (error) { toast.error(error instanceof Error ? error.message : 'Não foi possível concluir a ação.'); }
      finally { button.disabled = false; }
    }
  }
}

function createModal(title: string, eyebrow: string): HTMLElement {
  const overlay = createElement('section', { className: 'modal-overlay' });
  const card = createElement('article', { className: 'plant-card fatura-modal' });
  const header = createElement('div', { className: 'modal-header' });
  const heading = createElement('div');
  heading.append(createElement('span', { className: 'eyebrow', textContent: eyebrow }), createElement('h2', { textContent: title }));
  const close = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Fechar' });
  close.addEventListener('click', () => overlay.remove());
  header.append(heading, close);
  card.append(header, createElement('div', { className: 'modal-body' }));
  overlay.appendChild(card);
  overlay.addEventListener('click', (event) => { if (event.target === overlay) overlay.remove(); });
  document.body.appendChild(overlay);
  return overlay;
}

function selectField(label: string, options: Array<{ value: string; label: string }>, required = false) {
  const field = createElement('label', { className: 'form-field' });
  const select = createElement('select'); select.required = required;
  select.append(...options.map((item) => option(item.value, item.label)));
  field.append(createElement('span', { textContent: label }), select);
  return { field, select };
}
function textField(label: string, type: string, value: string, required = false) {
  const field = createElement('label', { className: 'form-field' });
  const input = createElement('input'); input.type = type; input.value = value; input.required = required;
  field.append(createElement('span', { textContent: label }), input);
  return { field, input };
}
function option(value: string, label: string): HTMLOptionElement { const element = createElement('option', { textContent: label }); element.value = value; return element; }
function filterSelect(label: string, value: string, options: Array<{ value: string; label: string }>, onChange: (value: string) => void): HTMLElement { const field = createElement('label', { className: 'faturas-filter-field' }); const select = createElement('select'); select.append(...options.map((item) => option(item.value, item.label))); select.value = value; select.addEventListener('change', () => onChange(select.value)); field.append(createElement('span', { textContent: label }), select); return field; }
function selectionCheckbox(label: string): HTMLInputElement { const input = createElement('input', { className: 'fatura-selection-checkbox' }); input.type = 'checkbox'; input.setAttribute('aria-label', label); input.addEventListener('click', (event) => event.stopPropagation()); return input; }
function createUcCell(fatura: FaturaRow): HTMLElement { const cell = createElement('div', { className: 'fatura-uc-cell' }); cell.append(createElement('strong', { textContent: fatura.ucCodigo }), createElement('span', { textContent: fatura.concessionaria ?? 'Concessionária não informada' })); return cell; }
function createStatusBadge(status: FaturaStatus): HTMLElement { const tone = status === 'received' ? 'success' : status === 'overdue' ? 'danger' : status === 'pending' ? 'warning' : 'neutral'; return createElement('span', { className: tone === 'neutral' ? 'status-badge' : `status-badge tone-${tone}`, textContent: statusLabel(status) }); }
function statusLabel(status: FaturaStatus): string { return ({ pending: 'Pendente', received: 'Recebida', overdue: 'Vencida', canceled: 'Cancelada', refunded: 'Estornada' })[status]; }
function formatCurrency(value: string | number): string { return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(Number(value)); }
function formatDate(value: string): string { return value ? new Date(`${value.slice(0, 10)}T12:00:00`).toLocaleDateString('pt-BR') : '-'; }
function formatReference(value: string): string { if (!/^\d{4}-\d{2}$/.test(value)) return value || '-'; const [year, month] = value.split('-'); return `${month}/${year}`; }
function currentMonth(): string { const now = new Date(); return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`; }
function normalize(value: string): string { return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase(); }
