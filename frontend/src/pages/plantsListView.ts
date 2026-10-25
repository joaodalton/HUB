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
  searchInput.placeholder = 'Pesquisar usinas...';
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
  newPlantButton.append(createIcon('plus'), document.createTextNode('Nova Usina'));
  newPlantButton.addEventListener('click', () => ctx.onNewPlant());
  const importButton = createElement('button', { className: 'secondary-button', textContent: 'Importação/exportação', type: 'button' });
  importButton.addEventListener('click', () => ctx.onImport());

  const archiveButton = createElement('button', { className: 'secondary-button', textContent: 'Arquivo ▾', type: 'button' });
  archiveButton.disabled = true;
  archiveButton.title = 'Importacao/exportacao em planilha -- em breve';

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
      { label: 'Potência total', value: `${formatValue(totalPotencia)} kWp`, chipColor: 'blue', icon: 'plants' },
      { label: 'Ocupação média', value: `${formatValue(ocupacaoMedia)}%`, chipColor: 'amber', icon: 'rateio' },
      { label: 'UCs vinculadas', value: String(totalUcs), chipColor: 'green', icon: 'ucs' },
      { label: 'Geração estimada', value: `${formatValue(geracaoEstimada)} kWh`, chipColor: 'purple', icon: 'agenda' }
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
      ['Todas', null, summary.total],
      ['Ativas', 'Online', summary.ativas],
      ['Em implantação', 'Implantacao', summary.emImplantacao],
      ['Manutenção', 'Manutencao', summary.manutencao]
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
      title: 'Usinas cadastradas',
      eyebrow: 'Listagem',
      rows: paged.rows,
      emptyMessage: loadError
        ? 'Nao foi possivel carregar usinas.'
        : isFiltered
          ? 'Nenhuma usina encontrada para esse filtro.'
          : 'Nenhuma usina cadastrada ainda.',
      state: isLoading ? 'loading' : loadError ? 'error' : isFiltered ? 'filtered' : 'ready',
      stateTitle: loadError ? 'Nao foi possivel carregar usinas' : isFiltered ? 'Nenhuma usina corresponde aos filtros' : 'Nenhuma usina cadastrada',
      emptyAction: { label: 'Limpar filtros', onClick: () => { ctx.setSearchTerm(''); ctx.setStatusFilter(null); ctx.setPage(1); writeListState({ busca: null, status: null, pagina: null }); refresh(); } },
      errorAction: { label: 'Tentar novamente', onClick: () => ctx.onRetry() },
      onRowClick: (plant) => ctx.onSelectPlant(plant),
      columns: [
        { key: 'id', label: 'ID', render: (plant) => `#${plant.id}` },
        { key: 'nome', label: 'Nome da usina', render: (plant) => plant.nome },
        { key: 'kwPico', label: 'Potência (kWp)', align: 'right' },
        { key: 'ucsConectadas', label: 'UCs conectadas', align: 'right', render: (plant) => String(connectedUcs(allUcs, plant.id).length) },
        {
          key: 'status',
          label: 'Status',
          render: (plant) => createStatusDotLabel(plantStatusLabel(plant.status), plantStatusTone(plant.status))
        },
        { key: 'cidadeUf', label: 'Cidade/UF', render: (plant) => plantLocationLabel(plant) },
        { key: 'endereco', label: 'Endereço', defaultVisible: false, render: (plant) => plant.endereco || 'Não informado' },
        { key: 'dataAtivacao', label: 'Data de ativação', defaultVisible: false, render: (plant) => plant.dataAtivacao || 'Não informado' },
        { key: 'responsavel', label: 'Responsável', defaultVisible: false, render: (plant) => plant.responsavel || 'Não informado' },
        { key: 'marcaInversor', label: 'Marca do inversor', defaultVisible: false, render: (plant) => plant.marcaInversor || 'Não informado' },
        { key: 'telefoneProprietario', label: 'Telefone do proprietário', defaultVisible: false, render: (plant) => plant.telefoneProprietario || 'Não informado' },
        { key: 'emailProprietario', label: 'Email do proprietário', defaultVisible: false, render: (plant) => plant.emailProprietario || 'Não informado' },
        { key: 'percentualConsumo', label: '% Consumo da geração', defaultVisible: false, align: 'right', render: (plant) => `${(100 - plant.percentualDisponivel).toFixed(1)}%` }
      ]
    });

    attachActionsRail(panel, paged.rows, createRowActionButtons);
    return panel;
  }

  function createRowActionButtons(plant: PlantRow): HTMLElement {
    const wrap = createElement('div', { className: 'table-row-actions' });

    const viewButton = createElement('button', { className: 'icon-button neutral', type: 'button' });
    viewButton.appendChild(createIcon('eye'));
    viewButton.title = 'Ver detalhes';
    attachTooltip(viewButton, `Ver detalhes de ${plant.nome}`);
    viewButton.setAttribute('aria-label', `Ver detalhes de ${plant.nome}`);
    viewButton.addEventListener('click', (event) => {
      event.stopPropagation();
      ctx.onSelectPlant(plant);
    });

    const editButton = createElement('button', { className: 'icon-button neutral', type: 'button' });
    editButton.appendChild(createIcon('edit'));
    editButton.title = 'Editar';
    attachTooltip(editButton, `Editar ${plant.nome}`);
    editButton.setAttribute('aria-label', `Editar ${plant.nome}`);
    editButton.addEventListener('click', (event) => {
      event.stopPropagation();
      ctx.onEditPlant(plant);
    });

    const deleteButton = createElement('button', { className: 'icon-button', type: 'button' });
    deleteButton.appendChild(createIcon('trash'));
    deleteButton.title = 'Excluir';
    attachTooltip(deleteButton, `Excluir ${plant.nome}`);
    deleteButton.setAttribute('aria-label', `Excluir ${plant.nome}`);
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
    const nav = createElement('nav', { className: 'faturas-pagination' });
    const previous = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Anterior' });
    previous.disabled = page <= 1; previous.addEventListener('click', () => { ctx.setPage(page - 1); writeListState({ pagina: page - 1 }); refresh(); });
    const next = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Próxima' });
    next.disabled = page >= pages || rows.length === 0; next.addEventListener('click', () => { ctx.setPage(page + 1); writeListState({ pagina: page + 1 }); refresh(); });
    nav.append(previous, createElement('span', { textContent: `${rows.length ? page : 0} de ${rows.length ? pages : 0}` }), next);
    return nav;
  }

  refresh();
  fragment.append(toolbar, filtersRow, statsHolder, tableHolder, paginationHolder);
  return fragment;
}
