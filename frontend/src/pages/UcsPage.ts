import { createDataTable } from '../components/DataTable';
import { createInfoField } from '../components/ClientDetailView';
import { createIcon } from '../components/Icon';
import { createIconStatCard, type IconStatCardProps } from '../components/IconStatCard';
import { createImportacoesModal } from '../components/ImportacoesModal';
import { createUcCard } from '../components/UcCard';
import { createUcBillingRuleSection } from '../components/UcBillingRuleSection';
import { createElement } from '../dom';
import {
  listBillingRuleAssignments, listBillingRules, type BillingRule, type BillingRuleAssignment
} from '../services/billingRulesService';
import { useGlobalLoading } from '../hooks/useGlobalLoading';
import { useToast } from '../hooks/useToast';
import { createBaseLayout } from '../layouts/BaseLayout';
import { getClients, type ClientRow } from '../services/clientsService';
import { getAvailablePlants, type PlantRow } from '../services/plantService';
import {
  createUc,
  deleteUc,
  getUcs,
  type UcPayload,
  type UcRow,
  updateUc
} from '../services/ucsService';
import { createDebouncedInput, matchesListSearch, pageSlice, readListParam, readPositiveListParam, writeListState } from '../services/listState';
import { createListPagination, formatUcDate, isContractExpiring } from './ucsShared';
import { t } from '../services/i18nService';

type UcTableRow = UcRow & { cliente: string; usina: string };
const PAGE_SIZE = 25;

export function createUcsPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const toast = useToast();
  const loading = useGlobalLoading();
  let ucs: UcRow[] = [];
  let clients: ClientRow[] = [];
  let availablePlants: PlantRow[] = [];
  const requestedUcId = Number(readListParam('ucId'));
  let selectedUcId: number | null = Number.isSafeInteger(requestedUcId) && requestedUcId > 0 ? requestedUcId : null;
  let billingRules: BillingRule[] = [];
  let billingAssignments: BillingRuleAssignment[] = [];
  let billingRulesUnavailable = false;
  let loadError = false;
  let isLoading = true;
  let quickFilter: 'all' | 'without-plant' | 'contract-expiring' = (readListParam('filtro') as 'all' | 'without-plant' | 'contract-expiring') ?? 'all';
  let searchTerm = readListParam('busca') ?? '';
  let page = readPositiveListParam('pagina');

  const layout = createBaseLayout({
    content,
    eyebrow: t('ucs.page.eyebrow'),
    title: t('ucs.page.title'),
    description: t('ucs.page.description')
  });

  const search = createElement('input'); search.type = 'search'; search.placeholder = t('ucs.search.placeholder'); search.setAttribute('aria-label', t('ucs.search.ariaLabel'));
  const applySearch = createDebouncedInput((value) => { if (value !== searchTerm) { searchTerm = value; page = 1; selectedUcId = null; writeListState({ busca: value || null, pagina: null, ucId: null }); renderContent(); } });
  search.addEventListener('input', () => applySearch(search.value));
  const filters = createElement('div', { className: 'page-actions' }); filters.appendChild(search);

  renderContent();
  loadAll();

  return layout;

  async function loadAll(): Promise<void> {
    isLoading = true;
    loading.show();
    try {
      [ucs, clients, availablePlants] = await Promise.all([getUcs(), getClients(), getAvailablePlants()]);
      loadError = false;
      try {
        [billingRules, billingAssignments] = await Promise.all([listBillingRules(), listBillingRuleAssignments({ ativo: 'true' })]);
        billingRulesUnavailable = false;
      } catch {
        billingRulesUnavailable = true;
      }
    } catch {
      loadError = true;
      toast.error(t('ucs.toast.loadError'));
    } finally {
      isLoading = false;
      loading.hide();
      renderContent();
    }
  }

  function renderContent(): void {
    const selectedUc = ucs.find((item) => item.id === selectedUcId) ?? null;

    const pageActions = createElement('div', { className: 'page-actions' });
    const spacer = createElement('div');
    spacer.style.flex = '1 0 auto';
    spacer.style.minWidth = '0';
    const newUcButton = createElement('button', { className: 'button-with-icon', type: 'button' });
    const importButton = createElement('button', { className: 'secondary-button', textContent: t('ucs.actions.import'), type: 'button' });
    newUcButton.append(createIcon('plus'), document.createTextNode(t('ucs.actions.new')));

    newUcButton.addEventListener('click', () => {
      if (clients.length === 0) {
        toast.error(t('ucs.toast.noClientForUc'));
        return;
      }
      openUcEditor(null);
    });
    importButton.addEventListener('click', () => document.body.appendChild(createImportacoesModal(() => void loadAll())));

    pageActions.append(spacer, importButton, newUcButton);

    const rows: UcTableRow[] = ucs.filter(matchesQuickFilter).filter((uc) => matchesListSearch(searchTerm, `${uc.codigo} ${uc.apelido} ${uc.clienteNome ?? ''} ${uc.concessionaria ?? ''} ${uc.conexoes.map((link) => link.usina).join(' ')}`)).map((uc) => ({
      ...uc,
      cliente: uc.clienteNome ?? '-',
      usina: uc.conexoes.length > 0 ? uc.conexoes.map((conexao) => conexao.usina).join(', ') : t('ucs.columns.usinaNone')
    }));

    const paged = pageSlice(rows, page, PAGE_SIZE); page = paged.page;
    const table = createDataTable<UcTableRow>({
      title: t('ucs.table.title'),
      eyebrow: t('ucs.table.eyebrow'),
      rows: paged.rows,
      emptyMessage: loadError
        ? t('ucs.table.loadError')
        : t('ucs.table.empty'),
      state: isLoading ? 'loading' : loadError ? 'error' : quickFilter !== 'all' || searchTerm ? 'filtered' : 'ready',
      stateTitle: loadError ? t('ucs.table.stateTitleError') : quickFilter !== 'all' || searchTerm ? t('ucs.table.stateTitleFiltered') : t('ucs.table.stateTitleEmpty'),
      emptyAction: { label: t('ucs.emptyAction.clearFilters'), onClick: () => { quickFilter = 'all'; searchTerm = ''; page = 1; writeListState({ busca: null, filtro: null, pagina: null }); renderContent(); } },
      errorAction: { label: t('ucs.errorAction.retry'), onClick: () => void loadAll() },
      onRowClick: (row) => {
        selectedUcId = row.id;
        writeListState({ ucId: row.id });
        renderContent();
      },
      columns: [
        { key: 'cliente', label: t('ucs.columns.cliente') },
        { key: 'codigo', label: t('ucs.columns.uc') },
        { key: 'usina', label: t('ucs.columns.usina') },
        { key: 'consumo', label: t('ucs.columns.consumo'), align: 'right' },
        { key: 'tipoLigacao', label: t('ucs.columns.ligacao') },
        { key: 'apelido', label: t('ucs.columns.apelido'), defaultVisible: false, render: (uc) => uc.apelido || t('ucs.notInformed') },
        { key: 'documento', label: t('ucs.columns.documento'), defaultVisible: false, render: (uc) => uc.documento || t('ucs.notInformed') },
        { key: 'endereco', label: t('ucs.columns.endereco'), defaultVisible: false, render: (uc) => uc.endereco || t('ucs.notInformed') },
        { key: 'cep', label: t('ucs.columns.cep'), defaultVisible: false, render: (uc) => uc.cep || t('ucs.notInformed') },
        { key: 'concessionaria', label: t('ucs.columns.concessionaria'), defaultVisible: false, render: (uc) => uc.concessionaria || t('ucs.notInformed') },
        { key: 'baseTarifaria', label: t('ucs.columns.baseTarifaria'), defaultVisible: false },
        { key: 'desconto', label: t('ucs.columns.desconto'), defaultVisible: false, render: (uc) => uc.desconto || '-' },
        { key: 'geracaoPropria', label: t('ucs.columns.geracaoPropria'), defaultVisible: false, render: (uc) => uc.geracaoPropria ? t('ucs.yes') : t('ucs.no') },
        { key: 'diaEmissaoFatura', label: t('ucs.columns.diaEmissaoFatura'), defaultVisible: false, render: (uc) => uc.diaEmissaoFatura != null ? String(uc.diaEmissaoFatura) : t('ucs.notInformed') },
        { key: 'inicioContrato', label: t('ucs.columns.inicioContrato'), defaultVisible: false, render: (uc) => formatUcDate(uc.inicioContrato) },
        { key: 'terminoContrato', label: t('ucs.columns.terminoContrato'), defaultVisible: false, render: (uc) => formatUcDate(uc.terminoContrato) },
        { key: 'carenciaMeses', label: t('ucs.columns.carenciaMeses'), defaultVisible: false, render: (uc) => uc.carenciaMeses != null ? String(uc.carenciaMeses) : t('ucs.notInformed') }
      ]
    });

    // `search` e `filters` vivem fora do renderContent (ver topo): recria-los a
    // cada render destruia o input com foco no meio da digitacao.
    if (search.value !== searchTerm) search.value = searchTerm;
    const blocks = [pageActions, filters, createQuickFilters(), createStatCards(), table, createListPagination(page, paged.pages, rows.length, (nextPage) => { page = nextPage; writeListState({ pagina: page }); renderContent(); })];

    if (!selectedUc) {
      content.replaceChildren(...blocks);
      return;
    }

    // Mesmo padrao de PendenciasPage.ts: coluna da esquerda com seu proprio
    // content-stack, painel de detalhe fixo (sticky) a direita.
    const listColumn = createElement('div', { className: 'content-stack' });
    listColumn.append(...blocks);

    const wrapper = createElement('div', { className: 'list-detail-grid' });
    wrapper.append(listColumn, createUcDetailPanel(selectedUc));
    content.replaceChildren(wrapper);
  }

  function createStatCards(): HTMLElement {
    const metrics: IconStatCardProps[] = [
      { label: t('ucs.stats.total'), value: String(ucs.length), chipColor: 'blue', icon: 'ucs' },
      { label: t('ucs.stats.withPlant'), value: String(ucs.filter((uc) => uc.conexoes.length > 0).length), chipColor: 'green', icon: 'plants' },
      { label: t('ucs.stats.withoutPlant'), value: String(ucs.filter((uc) => uc.conexoes.length === 0).length), chipColor: 'amber', icon: 'pending' }
    ];
    const grid = createElement('section', { className: 'metric-grid' });
    metrics.forEach((metric) => grid.appendChild(createIconStatCard(metric)));
    return grid;
  }

  function createQuickFilters(): HTMLElement {
    const filters = createElement('div', { className: 'filter-row uc-quick-filters' });
    [
      [t('ucs.filters.all'), 'all'],
      [t('ucs.filters.withoutPlant'), 'without-plant'],
      [t('ucs.filters.contractExpiring'), 'contract-expiring']
    ].forEach(([label, value]) => {
      const button = createElement('button', { className: quickFilter === value ? 'filter-chip active' : 'filter-chip', textContent: label, type: 'button' });
      button.addEventListener('click', () => {
        quickFilter = value as typeof quickFilter;
        page = 1; selectedUcId = null;
        writeListState({ filtro: quickFilter === 'all' ? null : quickFilter, pagina: null, ucId: null });
        renderContent();
      });
      filters.appendChild(button);
    });
    return filters;
  }

  function matchesQuickFilter(uc: UcRow): boolean {
    if (quickFilter === 'without-plant') return uc.conexoes.length === 0;
    if (quickFilter === 'contract-expiring') return isContractExpiring(uc.terminoContrato);
    return true;
  }

  // So-leitura -- reaproveita createInfoField (mesmo helper que
  // ClientDetailView.ts e PlantsPage.ts ja usam pro par label/valor), sem
  // secao de "Observacoes" a pedido. Acoes (Editar/Excluir) abrem o mesmo
  // UcCard.ts de sempre -- nenhuma mudanca nele.
  function createUcDetailPanel(uc: UcRow): HTMLElement {
    const panel = createElement('aside', { className: 'detail-info-panel sticky' });

    const title = createElement('div', { className: 'panel-title' });
    const titleText = createElement('div');
    const eyebrow = createElement('span', { className: 'eyebrow', textContent: t('ucs.detail.eyebrow') });
    const heading = createElement('h2', { textContent: uc.codigo || t('ucs.detail.headingFallback') });
    const closeButton = createElement('button', { className: 'icon-button neutral', type: 'button' });
    closeButton.appendChild(createIcon('x'));
    closeButton.title = t('ucs.detail.closeTitle');
    closeButton.addEventListener('click', () => {
      selectedUcId = null; writeListState({ ucId: null }, 'replace');
      renderContent();
    });

    titleText.append(eyebrow, heading);
    title.append(titleText, closeButton);

    const grid = createElement('div', { className: 'detail-info-grid' });
    grid.append(
      createInfoField(t('ucs.detail.labelCliente'), uc.clienteNome ?? '-'),
      createInfoField(t('ucs.detail.labelApelido'), uc.apelido || t('ucs.notInformed')),
      createInfoField(t('ucs.detail.labelDocumento'), uc.documento || t('ucs.notInformed')),
      createInfoField(t('ucs.detail.labelEndereco'), uc.endereco || t('ucs.notInformed')),
      createInfoField(t('ucs.detail.labelCep'), uc.cep || t('ucs.notInformed')),
      createInfoField(t('ucs.detail.labelConcessionaria'), uc.concessionaria || t('ucs.notInformed')),
      createInfoField(t('ucs.detail.labelConsumo'), uc.consumo != null ? String(uc.consumo) : '-'),
      createInfoField(t('ucs.detail.labelBaseTarifaria'), uc.baseTarifaria),
      createInfoField(t('ucs.detail.labelDesconto'), uc.desconto || '-'),
      createInfoField(t('ucs.detail.labelLigacao'), uc.tipoLigacao),
      createInfoField(t('ucs.detail.labelGeracaoPropria'), uc.geracaoPropria ? t('ucs.yes') : t('ucs.no')),
      createInfoField(t('ucs.detail.labelDiaEmissaoFatura'), uc.diaEmissaoFatura != null ? String(uc.diaEmissaoFatura) : t('ucs.notInformed')),
      createInfoField(t('ucs.detail.labelInicioContrato'), formatUcDate(uc.inicioContrato)),
      createInfoField(t('ucs.detail.labelTerminoContrato'), formatUcDate(uc.terminoContrato)),
      createInfoField(t('ucs.detail.labelCarenciaMeses'), uc.carenciaMeses != null ? String(uc.carenciaMeses) : t('ucs.notInformed')),
      createInfoField(t('ucs.detail.labelDescontoCarencia'), uc.percentualDescontoCarencia || t('ucs.notInformed')),
      createInfoField(
        t('ucs.detail.labelUsinasConectadas'),
        uc.conexoes.length > 0 ? uc.conexoes.map((conexao) => `${conexao.usina} (${conexao.percentual}%)`).join(', ') : t('ucs.detail.usinasNone')
      )
    );

    const actions = createElement('div', { className: 'form-actions' });
    const editButton = createElement('button', { className: 'secondary-button button-with-icon', type: 'button' });
    editButton.append(createIcon('edit'), document.createTextNode(t('ucs.actions.edit')));
    editButton.addEventListener('click', () => openUcEditor(uc));

    const deleteButton = createElement('button', { className: 'danger-button button-with-icon', type: 'button' });
    deleteButton.append(createIcon('trash'), document.createTextNode(t('ucs.actions.delete')));
    deleteButton.addEventListener('click', () => confirmDeleteUc(uc));

    actions.append(editButton, deleteButton);

    panel.append(title, grid, createUcBillingRuleSection({
      uc, rules: billingRules, assignments: billingAssignments,
      unavailable: billingRulesUnavailable, onUpdated: loadAll
    }), actions);
    return panel;
  }

  // Abre o UcCard.ts de sempre, como modal solto no body -- mesmo padrao ja
  // usado em PlantsPage.ts (openPlantEditor). Nenhuma mudanca no UcCard.ts.
  function openUcEditor(uc: UcRow | null): void {
    document.body.appendChild(createUcCard({
      uc: uc ?? undefined,
      clients,
      availablePlants,
      onCancel: () => {
        document.querySelector('.modal-overlay')?.remove();
      },
      onSave: async (data) => {
        await saveUc(uc, data);
        document.querySelector('.modal-overlay')?.remove();
        await loadAll();
      },
      onDelete: uc ? () => {
        document.querySelector('.modal-overlay')?.remove();
        confirmDeleteUc(uc);
      } : undefined
    }));
  }

  async function saveUc(existing: UcRow | null, data: UcPayload): Promise<void> {
    loading.show();
    try {
      if (existing) {
        await updateUc(existing.id, data);
        toast.success(t('ucs.toast.updated'));
      } else {
        await createUc(data);
        toast.success(t('ucs.toast.created'));
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('ucs.toast.saveError'));
    } finally {
      loading.hide();
    }
  }

  async function confirmDeleteUc(uc: UcRow): Promise<void> {
    const confirmed = window.confirm(`${t('ucs.confirmDelete.prefix')} ${uc.codigo}${t('ucs.confirmDelete.suffix')}`);
    if (!confirmed) return;

    loading.show();
    try {
      await deleteUc(uc.id);
      toast.success(t('ucs.toast.deleted'));
      if (selectedUcId === uc.id) selectedUcId = null;
      await loadAll();
    } catch {
      toast.error(t('ucs.toast.deleteError'));
    } finally {
      loading.hide();
    }
  }
}
