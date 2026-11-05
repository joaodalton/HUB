// frontend/src/pages/plantsListView.ts
// Lista de usinas (cards de status, busca, tabela) -- extraido de
// PlantsPage.ts (organizacao, sem mudanca de comportamento).
import { attachActionsRail, createDataTable } from '../components/DataTable';
import { createIcon } from '../components/Icon';
import { createIconStatCard, type IconStatCardProps } from '../components/IconStatCard';
import { attachTooltip } from '../components/Tooltip';
import { createElement } from '../dom';
import { getPlantStatusSummary, plantStatusLabel, plantStatusTone, type PlantRow } from '../services/plantService';
import type { UcRow } from '../services/ucsService';
import { createDebouncedInput, pageSlice, writeListState } from '../services/listState';
import { t } from '../services/i18nService';
import { connectedUcs, createStatusDotLabel, formatValue, normalize, plantLocationLabel } from './plantsShared';

export type PlantsListContext = {
  getPlants: () => PlantRow[];
  getAllUcs: () => UcRow[];
  isLoading: () => boolean;
  loadError: () => boolean;
  getSearchTerm: () => string;
  setSearchTerm: (value: string) => void;
  getStatusFilter: () => string | null;
  setStatusFilter: (value: string | null) => void;
  getPage: () => number;
  setPage: (value: number) => void;
  clearSelection: () => void;
  onRetry: () => void;
  onSelectPlant: (plant: PlantRow) => void;
  onNewPlant: () => void;
  onImport: () => void;
  onEditPlant: (plant: PlantRow) => void;
  onDeletePlant: (plant: PlantRow) => void;
};

function getFilteredPlants(ctx: PlantsListContext): PlantRow[] {
  const searchTerm = ctx.getSearchTerm();
  const statusFilter = ctx.getStatusFilter();

  return ctx.getPlants().filter((plant) => {
    if (statusFilter && plant.status !== statusFilter) return false;

    if (searchTerm) {
      const haystack = normalize(`${plant.id} ${plant.nome} ${plant.cidade ?? ''} ${plant.uf ?? ''}`);
      if (!haystack.includes(normalize(searchTerm))) return false;
    }

    return true;
  });
}

// Toolbar (busca + acoes) e criada uma vez so; refresh() troca apenas os
// holders de cards/tabela por baixo -- assim o campo de busca nunca perde
// foco enquanto o usuario digita (replaceChildren no fragmento inteiro a
// cada tecla apagaria o input e o cursor).
export function renderPlantsListView(ctx: PlantsListContext): HTMLElement {
  const fragment = createElement('div', { className: 'content-stack' });
  const toolbar = createElement('div', { className: 'page-actions' });

  const searchInput = createElement('input');
  searchInput.type = 'text';
  searchInput.placeholder = t('plants.search.placeholder');
  searchInput.value = ctx.getSearchTerm();
  const applySearch = createDebouncedInput((value) => {
    if (value !== ctx.getSearchTerm()) {
      ctx.setSearchTerm(value);
      ctx.setPage(1);
      ctx.clearSelection();
      writeListState({ busca: value || null, pagina: null, selecionada: null });
      refresh();
    }
  });
  searchInput.addEventListener('input', () => applySearch(searchInput.value));

  const spacer = createElement('div');
  spacer.style.flex = '1 0 auto';
  spacer.style.minWidth = '0';

  const newPlantButton = createElement('button', { className: 'button-with-icon', type: 'button' });
  newPlantButton.append(createIcon('plus'), document.createTextNode(t('plants.actions.new')));
  newPlantButton.addEventListener('click', () => ctx.onNewPlant());
  const importButton = createElement('button', { className: 'secondary-button', textContent: t('plants.actions.import'), type: 'button' });
  importButton.addEventListener('click', () => ctx.onImport());

  const archiveButton = createElement('button', { className: 'secondary-button', textContent: t('plants.actions.archive'), type: 'button' });
  archiveButton.disabled = true;
  archiveButton.title = t('plants.actions.archiveTitle');

  toolbar.append(importButton, newPlantButton, archiveButton);

  const filtersRow = createElement('div', { className: 'page-actions' });
  const statusFiltersHolder = createElement('div');
  filtersRow.append(searchInput, spacer, statusFiltersHolder);

  const statsHolder = createElement('div');
  const tableHolder = createElement('div');
  const paginationHolder = createElement('div');

  function refresh(): void {
    statusFiltersHolder.replaceChildren(createStatusFilters());
    statsHolder.replaceChildren(createStatCards());
    tableHolder.replaceChildren(createPlantsTable());
    paginationHolder.replaceChildren(createPagination());
  }

  function createStatCards(): HTMLElement {
    const plants = ctx.getPlants();
    const allUcs = ctx.getAllUcs();
    const totalPotencia = plants.reduce((sum, plant) => sum + Number(plant.kwPico || 0), 0);
    const totalUcs = plants.reduce((sum, plant) => sum + connectedUcs(allUcs, plant.id).length, 0);
    const ocupacaoMedia = plants.length
      ? plants.reduce((sum, plant) => sum + (100 - plant.percentualDisponivel), 0) / plants.length
      : 0;
    const geracaoEstimada = plants.reduce((sum, plant) => sum + (plant.producaoMedia ?? 0), 0);
    const metrics: IconStatCardProps[] = [
      { label: t('plants.stats.totalPower'), value: `${formatValue(totalPotencia)} kWp`, chipColor: 'blue', icon: 'plants' },
      { label: t('plants.stats.avgOccupancy'), value: `${formatValue(ocupacaoMedia)}%`, chipColor: 'amber', icon: 'rateio' },
      { label: t('plants.stats.connectedUcs'), value: String(totalUcs), chipColor: 'green', icon: 'ucs' },
      { label: t('plants.stats.estimatedGeneration'), value: `${formatValue(geracaoEstimada)} kWh`, chipColor: 'purple', icon: 'agenda' }
    ];
    const grid = createElement('section', { className: 'metric-grid' });
    metrics.forEach((metric) => grid.appendChild(createIconStatCard(metric)));
    return grid;
  }

  function createStatusFilters(): HTMLElement {
    const summary = getPlantStatusSummary(ctx.getPlants());
    const statusFilter = ctx.getStatusFilter();
    const filters = createElement('div', { className: 'plant-status-filters' });
    [
      [t('plants.filters.all'), null, summary.total],
      [t('plants.filters.active'), 'Online', summary.ativas],
      [t('plants.filters.implementing'), 'Implantacao', summary.emImplantacao],
      [t('plants.filters.maintenance'), 'Manutencao', summary.manutencao]
    ].forEach(([label, status, count]) => {
      const button = createElement('button', { className: statusFilter === status ? 'filter-chip active' : 'filter-chip', textContent: `${label} ${count}`, type: 'button' });
      button.addEventListener('click', () => {
        ctx.setStatusFilter(status as string | null);
        ctx.setPage(1); ctx.clearSelection();
        writeListState({ status: status as string | null, pagina: null, selecionada: null });
        refresh();
      });
      filters.appendChild(button);
    });
    return filters;
  }

  function createPlantsTable(): HTMLElement {
    const isLoading = ctx.isLoading();
    const loadError = ctx.loadError();
    const allUcs = ctx.getAllUcs();
    const filteredRows = getFilteredPlants(ctx);
    const paged = pageSlice(filteredRows, ctx.getPage(), 25); ctx.setPage(paged.page);
    const isFiltered = Boolean(ctx.getSearchTerm() || ctx.getStatusFilter());

    const panel = createDataTable<PlantRow>({
      title: t('plants.table.title'),
      eyebrow: t('plants.table.eyebrow'),
      rows: paged.rows,
      emptyMessage: loadError
        ? t('plants.table.loadError')
        : isFiltered
          ? t('plants.table.emptyFiltered')
          : t('plants.table.emptyDefault'),
      state: isLoading ? 'loading' : loadError ? 'error' : isFiltered ? 'filtered' : 'ready',
      stateTitle: loadError ? t('plants.table.stateTitleError') : isFiltered ? t('plants.table.stateTitleFiltered') : t('plants.table.stateTitleEmpty'),
      emptyAction: { label: t('plants.emptyAction.clearFilters'), onClick: () => { ctx.setSearchTerm(''); ctx.setStatusFilter(null); ctx.setPage(1); writeListState({ busca: null, status: null, pagina: null }); refresh(); } },
      errorAction: { label: t('plants.errorAction.retry'), onClick: () => ctx.onRetry() },
      onRowClick: (plant) => ctx.onSelectPlant(plant),
      columns: [
        { key: 'id', label: t('plants.columns.id'), render: (plant) => `#${plant.id}` },
        { key: 'nome', label: t('plants.columns.nome'), render: (plant) => plant.nome },
        { key: 'kwPico', label: t('plants.columns.kwPico'), align: 'right' },
        { key: 'ucsConectadas', label: t('plants.columns.ucsConectadas'), align: 'right', render: (plant) => String(connectedUcs(allUcs, plant.id).length) },
        {
          key: 'status',
          label: t('plants.columns.status'),
          render: (plant) => createStatusDotLabel(plantStatusLabel(plant.status), plantStatusTone(plant.status))
        },
        { key: 'cidadeUf', label: t('plants.columns.cidadeUf'), render: (plant) => plantLocationLabel(plant) },
        { key: 'endereco', label: t('plants.columns.endereco'), defaultVisible: false, render: (plant) => plant.endereco || t('plants.notInformed') },
        { key: 'dataAtivacao', label: t('plants.columns.dataAtivacao'), defaultVisible: false, render: (plant) => plant.dataAtivacao || t('plants.notInformed') },
        { key: 'responsavel', label: t('plants.columns.responsavel'), defaultVisible: false, render: (plant) => plant.responsavel || t('plants.notInformed') },
        { key: 'marcaInversor', label: t('plants.columns.marcaInversor'), defaultVisible: false, render: (plant) => plant.marcaInversor || t('plants.notInformed') },
        { key: 'telefoneProprietario', label: t('plants.columns.telefoneProprietario'), defaultVisible: false, render: (plant) => plant.telefoneProprietario || t('plants.notInformed') },
        { key: 'emailProprietario', label: t('plants.columns.emailProprietario'), defaultVisible: false, render: (plant) => plant.emailProprietario || t('plants.notInformed') },
        { key: 'percentualConsumo', label: t('plants.columns.percentualConsumo'), defaultVisible: false, align: 'right', render: (plant) => `${(100 - plant.percentualDisponivel).toFixed(1)}%` }
      ]
    });

    attachActionsRail(panel, paged.rows, createRowActionButtons);
    return panel;
  }

  function createRowActionButtons(plant: PlantRow): HTMLElement {
    const wrap = createElement('div', { className: 'table-row-actions' });

    const viewButton = createElement('button', { className: 'icon-button neutral', type: 'button' });
    viewButton.appendChild(createIcon('eye'));
    viewButton.title = t('plants.rowActions.viewTitle');
    attachTooltip(viewButton, `${t('plants.rowActions.viewAriaPrefix')} ${plant.nome}`);
    viewButton.setAttribute('aria-label', `${t('plants.rowActions.viewAriaPrefix')} ${plant.nome}`);
    viewButton.addEventListener('click', (event) => {
      event.stopPropagation();
      ctx.onSelectPlant(plant);
    });

    const editButton = createElement('button', { className: 'icon-button neutral', type: 'button' });
    editButton.appendChild(createIcon('edit'));
    editButton.title = t('plants.rowActions.editTitle');
    attachTooltip(editButton, `${t('plants.rowActions.editAriaPrefix')} ${plant.nome}`);
    editButton.setAttribute('aria-label', `${t('plants.rowActions.editAriaPrefix')} ${plant.nome}`);
    editButton.addEventListener('click', (event) => {
      event.stopPropagation();
      ctx.onEditPlant(plant);
    });

    const deleteButton = createElement('button', { className: 'icon-button', type: 'button' });
    deleteButton.appendChild(createIcon('trash'));
    deleteButton.title = t('plants.rowActions.deleteTitle');
    attachTooltip(deleteButton, `${t('plants.rowActions.deleteAriaPrefix')} ${plant.nome}`);
    deleteButton.setAttribute('aria-label', `${t('plants.rowActions.deleteAriaPrefix')} ${plant.nome}`);
    deleteButton.addEventListener('click', (event) => {
      event.stopPropagation();
      ctx.onDeletePlant(plant);
    });

    wrap.append(viewButton, editButton, deleteButton);
    return wrap;
  }

  function createPagination(): HTMLElement {
    const rows = getFilteredPlants(ctx); const pages = Math.max(1, Math.ceil(rows.length / 25));
    const page = ctx.getPage();
    const nav = createElement('nav', { className: 'faturas-pagination pagination-left' });
    const previous = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('plants.pagination.previous') });
    previous.disabled = page <= 1; previous.addEventListener('click', () => { ctx.setPage(page - 1); writeListState({ pagina: page - 1 }); refresh(); });
    const next = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('plants.pagination.next') });
    next.disabled = page >= pages || rows.length === 0; next.addEventListener('click', () => { ctx.setPage(page + 1); writeListState({ pagina: page + 1 }); refresh(); });
    nav.append(previous, createElement('span', { textContent: `${rows.length ? page : 0} ${t('plants.pagination.of')} ${rows.length ? pages : 0}` }), next);
    return nav;
  }

  refresh();
  fragment.append(toolbar, filtersRow, statsHolder, tableHolder, paginationHolder);
  return fragment;
}
