// frontend/src/pages/PlantsPage.ts
import { createDashboardCards, type DashboardMetric } from '../components/DashboardCards';
import { createDataTable } from '../components/DataTable';
import { createInfoField } from '../components/ClientDetailView';
import { createIcon } from '../components/Icon';
import { createPlantCard, type PlantFormData } from '../components/PlantCard';
import { createElement } from '../dom';
import { useGlobalLoading } from '../hooks/useGlobalLoading';
import { useToast } from '../hooks/useToast';
import { createBaseLayout } from '../layouts/BaseLayout';
import {
  createPlant,
  deletePlant,
  getPlantStatusSummary,
  getPlants,
  plantStatusLabel,
  plantStatusTone,
  removePlantConnection,
  type PlantRow,
  type PlantStatusTone,
  updatePlant
} from '../services/plantService';
import { getUcs, type UcRow } from '../services/ucsService';

type ConnectedUcRow = {
  id: number;
  connectionId: number;
  codigo: string;
  apelido: string;
  cliente: string;
  percentual: string;
  status: string;
};

// Abas sem backend ainda (Documentos de usina, Financeiro = V3.0, Historico e
// Logs nem tem model hoje) -- visiveis mas desabilitadas, mesmo padrao do
// ClientDetailView.ts.
const upcomingPlantTabs = ['Documentos', 'Financeiro', 'Histórico', 'Logs'];

export function createPlantsPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const toast = useToast();
  const loading = useGlobalLoading();
  let plants: PlantRow[] = [];
  let allUcs: UcRow[] = [];
  let selectedPlantId: number | null = null;
  let loadError = false;
  let searchTerm = '';
  let statusFilter: string | null = null;

  const layout = createBaseLayout({
    content,
    eyebrow: 'Usinas',
    title: 'Visualize geracao, uso e status das usinas'
  });

  loadPlants();

  return layout;

  async function loadPlants(): Promise<void> {
    loading.show();
    try {
      [plants, allUcs] = await Promise.all([getPlants(), getUcs()]);
      loadError = false;
    } catch {
      loadError = true;
      toast.error('Nao foi possivel carregar usinas. Verifique se o backend esta rodando.');
    } finally {
      loading.hide();
      renderContent();
    }
  }

  function connectedUcs(plantId: number): ConnectedUcRow[] {
    const rows: ConnectedUcRow[] = [];

    allUcs.forEach((uc) => {
      uc.conexoes
        .filter((conexao) => conexao.plantId === plantId)
        .forEach((conexao) => {
          rows.push({
            id: uc.id,
            connectionId: conexao.id,
            codigo: uc.codigo || 'Sem codigo',
            apelido: uc.apelido || uc.clienteNome || 'Sem apelido',
            cliente: uc.clienteNome ?? '-',
            percentual: `${conexao.percentual}%`,
            status: 'Ativa'
          });
        });
    });

    return rows;
  }

  function getFilteredPlants(): PlantRow[] {
    return plants.filter((plant) => {
      if (statusFilter && plant.status !== statusFilter) return false;

      if (searchTerm) {
        const haystack = normalize(`${plant.id} ${plant.nome} ${plant.cidade ?? ''} ${plant.uf ?? ''}`);
        if (!haystack.includes(normalize(searchTerm))) return false;
      }

      return true;
    });
  }

  function renderContent(): void {
    const selectedPlant = plants.find((item) => item.id === selectedPlantId) ?? null;
    content.replaceChildren(selectedPlant ? renderDetailView(selectedPlant) : renderListView());
  }

  // Toolbar (busca + acoes) e criada uma vez so; refresh() troca apenas os
  // holders de cards/tabela por baixo -- assim o campo de busca nunca perde
  // foco enquanto o usuario digita (replaceChildren no fragmento inteiro a
  // cada tecla apagaria o input e o cursor).
  function renderListView(): HTMLElement {
    const fragment = createElement('div', { className: 'content-stack' });
    const toolbar = createElement('div', { className: 'page-actions' });

    const searchInput = createElement('input');
    searchInput.type = 'text';
    searchInput.placeholder = 'Pesquisar usinas...';
    searchInput.value = searchTerm;
    searchInput.addEventListener('input', () => {
      searchTerm = searchInput.value;
      refresh();
    });

    const filtersButton = createElement('button', { className: 'secondary-button', textContent: 'Filtros', type: 'button' });
    filtersButton.disabled = true;
    filtersButton.title = 'Em breve';

    const spacer = createElement('div');
    spacer.style.flex = '1 0 auto';
    spacer.style.minWidth = '0';

    const newPlantButton = createElement('button', { className: 'button-with-icon', type: 'button' });
    newPlantButton.append(createIcon('plus'), document.createTextNode('Nova Usina'));
    newPlantButton.addEventListener('click', () => openPlantEditor(null));

    const archiveButton = createElement('button', { className: 'secondary-button', textContent: 'Arquivo ▾', type: 'button' });
    archiveButton.disabled = true;
    archiveButton.title = 'Importacao/exportacao em planilha -- em breve';

    toolbar.append(searchInput, filtersButton, spacer, newPlantButton, archiveButton);

    const statsHolder = createElement('div');
    const tableHolder = createElement('div');

    function refresh(): void {
      statsHolder.replaceChildren(createStatCards());
      tableHolder.replaceChildren(createPlantsTable());
    }

    function createStatCards(): HTMLElement {
      const summary = getPlantStatusSummary(plants);
      const metrics: DashboardMetric[] = [
        {
          label: 'Ativas',
          value: String(summary.ativas),
          tone: 'success',
          icon: 'plants',
          active: statusFilter === 'Online',
          onClick: () => {
            statusFilter = statusFilter === 'Online' ? null : 'Online';
            refresh();
          }
        },
        {
          label: 'Em Implantação',
          value: String(summary.emImplantacao),
          tone: 'warning',
          icon: 'pending',
          active: statusFilter === 'Implantacao',
          onClick: () => {
            statusFilter = statusFilter === 'Implantacao' ? null : 'Implantacao';
            refresh();
          }
        },
        {
          label: 'Manutenção',
          value: String(summary.manutencao),
          tone: 'danger',
          icon: 'settings',
          active: statusFilter === 'Manutencao',
          onClick: () => {
            statusFilter = statusFilter === 'Manutencao' ? null : 'Manutencao';
            refresh();
          }
        },
        { label: 'Total', value: String(summary.total), tone: 'neutral', icon: 'documents' }
      ];

      return createDashboardCards(metrics);
    }

    function createPlantsTable(): HTMLElement {
      const rows = getFilteredPlants();
      const isFiltered = Boolean(searchTerm || statusFilter);

      return createDataTable<PlantRow>({
        title: 'Usinas cadastradas',
        eyebrow: 'Listagem',
        rows,
        emptyMessage: loadError
          ? 'Nao foi possivel carregar usinas.'
          : isFiltered
            ? 'Nenhuma usina encontrada para esse filtro.'
            : 'Nenhuma usina cadastrada ainda.',
        onRowClick: (plant) => {
          selectedPlantId = plant.id;
          renderContent();
        },
        columns: [
          { key: 'nome', label: 'Nome da usina', render: (plant) => createIdNameCell(`#${plant.id}`, plant.nome) },
          { key: 'kwPico', label: 'Potência (kWp)', align: 'right' },
          { key: 'ucsConectadas', label: 'UCs conectadas', align: 'right', render: (plant) => String(connectedUcs(plant.id).length) },
          {
            key: 'status',
            label: 'Status',
            render: (plant) => createStatusDotLabel(plantStatusLabel(plant.status), plantStatusTone(plant.status))
          },
          { key: 'cidadeUf', label: 'Cidade/UF', render: (plant) => plantLocationLabel(plant) },
          { key: 'acao', label: 'Ação', align: 'right', render: (plant) => createRowActionButtons(plant) }
        ]
      });
    }

    refresh();
    fragment.append(toolbar, statsHolder, tableHolder);
    return fragment;
  }

  function createRowActionButtons(plant: PlantRow): HTMLElement {
    const wrap = createElement('div', { className: 'table-row-actions' });

    const viewButton = createElement('button', { className: 'icon-button neutral', type: 'button' });
    viewButton.appendChild(createIcon('eye'));
    viewButton.title = 'Ver detalhes';
    viewButton.setAttribute('aria-label', `Ver detalhes de ${plant.nome}`);
    viewButton.addEventListener('click', (event) => {
      event.stopPropagation();
      selectedPlantId = plant.id;
      renderContent();
    });

    const editButton = createElement('button', { className: 'icon-button neutral', type: 'button' });
    editButton.appendChild(createIcon('edit'));
    editButton.title = 'Editar';
    editButton.setAttribute('aria-label', `Editar ${plant.nome}`);
    editButton.addEventListener('click', (event) => {
      event.stopPropagation();
      openPlantEditor(plant);
    });

    const deleteButton = createElement('button', { className: 'icon-button', type: 'button' });
    deleteButton.appendChild(createIcon('trash'));
    deleteButton.title = 'Excluir';
    deleteButton.setAttribute('aria-label', `Excluir ${plant.nome}`);
    deleteButton.addEventListener('click', (event) => {
      event.stopPropagation();
      confirmDeletePlant(plant);
    });

    wrap.append(viewButton, editButton, deleteButton);
    return wrap;
  }

  function renderDetailView(plant: PlantRow): HTMLElement {
    const wrapper = createElement('section', { className: 'client-detail-view' });

    const backLink = createElement('a', { className: 'detail-back-link', textContent: '← Usinas' });
    backLink.href = '#';
    backLink.addEventListener('click', (event) => {
      event.preventDefault();
      selectedPlantId = null;
      renderContent();
    });

    const columns = createElement('div', { className: 'detail-columns' });
    columns.append(createPlantInfoPanel(plant), createPlantSummaryPanel(plant));

    wrapper.append(backLink, createPlantDetailHeader(plant), columns, createPlantTabsPanel(plant));
    return wrapper;
  }

  function createPlantDetailHeader(plant: PlantRow): HTMLElement {
    const header = createElement('div', { className: 'detail-header' });
    const titleRow = createElement('div', { className: 'detail-title-row' });
    const idTag = createElement('span', { className: 'cell-id-tag', textContent: `#${plant.id}` });
    const heading = createElement('h2', { textContent: plant.nome });
    const tone = plantStatusTone(plant.status);
    const badge = createElement('span', {
      className: tone === 'neutral' ? 'status-badge' : `status-badge tone-${tone}`,
      textContent: plantStatusLabel(plant.status)
    });

    const actions = createElement('div', { className: 'detail-actions' });
    const editButton = createElement('button', { className: 'secondary-button button-with-icon', type: 'button' });
    editButton.append(createIcon('edit'), document.createTextNode('Editar'));
    const deleteButton = createElement('button', { className: 'danger-button button-with-icon', type: 'button' });
    deleteButton.append(createIcon('trash'), document.createTextNode('Excluir'));

    editButton.addEventListener('click', () => openPlantEditor(plant));
    deleteButton.addEventListener('click', () => confirmDeletePlant(plant));

    titleRow.append(idTag, heading, badge);
    actions.append(editButton, deleteButton);
    header.append(titleRow, actions);

    return header;
  }

  function createPlantInfoPanel(plant: PlantRow): HTMLElement {
    const panel = createElement('aside', { className: 'detail-info-panel' });
    const eyebrow = createElement('span', { className: 'eyebrow', textContent: 'Informações gerais' });
    const grid = createElement('div', { className: 'detail-info-grid' });

    grid.append(
      createInfoField('Potência (kWp)', plant.kwPico),
      createInfoField('Cidade/UF', plantLocationLabel(plant)),
      createInfoField('Endereço', plant.endereco || 'Não informado'),
      createInfoField('Data de ativação', plant.dataAtivacao || 'Não informado'),
      createInfoField('Responsável', plant.responsavel || 'Não informado'),
      createInfoField('UCs conectadas', String(connectedUcs(plant.id).length)),
      createInfoField('Marca do inversor', plant.marcaInversor || 'Não informado'),
      createInfoField('Telefone do proprietário', plant.telefoneProprietario || 'Não informado'),
      createInfoField('Email do proprietário', plant.emailProprietario || 'Não informado')
    );

    panel.append(eyebrow, grid);
    return panel;
  }

  function createPlantSummaryPanel(plant: PlantRow): HTMLElement {
    const panel = createElement('aside', { className: 'detail-info-panel plant-summary-panel' });
    const eyebrow = createElement('span', { className: 'eyebrow', textContent: 'Resumo' });
    const rows = createElement('div', { className: 'plant-summary-rows' });
    const activeCount = connectedUcs(plant.id).length;

    // "UCs disponiveis" / "UCs aguardando" nao tem contrapartida no backend
    // ainda (nao existe esse conceito no model hoje) -- mostrando "-" em vez
    // de inventar numero. "UCs ativas" e real (contagem de PlantConnection).
    rows.append(
      createSummaryRow('UCs ativas', String(activeCount)),
      createSummaryRow('UCs disponíveis', '-'),
      createSummaryRow('UCs aguardando', '-')
    );

    const occupied = Math.max(0, Math.min(100, 100 - plant.percentualDisponivel));
    const occupancy = createElement('div', { className: 'plant-summary-occupancy' });
    occupancy.append(createSummaryRow('% Ocupação', `${occupied}%`), createOccupancyBar(occupied));

    panel.append(eyebrow, rows, occupancy);
    return panel;
  }

  function createPlantTabsPanel(plant: PlantRow): HTMLElement {
    const panel = createElement('section', { className: 'detail-tabs-panel' });
    const tabs = createElement('div', { className: 'detail-tabs' });
    const ucsTab = createElement('button', { className: 'detail-tab active', textContent: 'UCs conectadas', type: 'button' });

    tabs.appendChild(ucsTab);

    upcomingPlantTabs.forEach((label) => {
      const tab = createElement('button', { className: 'detail-tab disabled', textContent: label, type: 'button' });
      tab.disabled = true;
      tab.title = 'Em breve';
      tabs.appendChild(tab);
    });

    panel.append(tabs, createConnectedUcsTable(plant));
    return panel;
  }

  function createConnectedUcsTable(plant: PlantRow): HTMLElement {
    const rows = connectedUcs(plant.id);

    return createDataTable<ConnectedUcRow>({
      title: 'UCs conectadas',
      eyebrow: 'Rateio',
      rows,
      emptyMessage: 'Nenhuma UC conectada a esta usina ainda.',
      columns: [
        { key: 'uc', label: 'UC', render: (row) => createIdNameCell(row.codigo, row.apelido) },
        { key: 'cliente', label: 'Cliente' },
        { key: 'percentual', label: '% Rateio', align: 'right' },
        { key: 'status', label: 'Status', render: (row) => createStatusDotLabel(row.status, 'success') },
        { key: 'acao', label: '', align: 'right', render: (row) => createRemoveConnectionButton(plant, row) }
      ]
    });
  }

  function createRemoveConnectionButton(plant: PlantRow, row: ConnectedUcRow): HTMLElement {
    const button = createElement('button', { className: 'icon-button', type: 'button' });
    button.appendChild(createIcon('x'));
    button.title = 'Desconectar da usina';
    button.setAttribute('aria-label', `Desconectar ${row.codigo} da usina`);
    button.addEventListener('click', () => confirmRemoveConnection(plant, row));
    return button;
  }

  async function confirmRemoveConnection(plant: PlantRow, row: ConnectedUcRow): Promise<void> {
    const confirmed = window.confirm(`Desconectar a UC ${row.codigo} desta usina? O percentual de rateio dela sera perdido.`);
    if (!confirmed) return;

    loading.show();
    try {
      await removePlantConnection(plant.id, row.connectionId);
      toast.success('UC desconectada.');
      await loadPlants();
    } catch {
      toast.error('Nao foi possivel desconectar a UC.');
    } finally {
      loading.hide();
    }
  }

  function openPlantEditor(plant: PlantRow | null): void {
    document.body.appendChild(createPlantCard({
      plant: plant ?? undefined,
      onCancel: () => {
        document.querySelector('.modal-overlay')?.remove();
      },
      onSave: async (data) => {
        await savePlant(plant, data);
        document.querySelector('.modal-overlay')?.remove();
        await loadPlants();
      },
      onDelete: plant ? () => {
        document.querySelector('.modal-overlay')?.remove();
        confirmDeletePlant(plant);
      } : undefined
    }));
  }

  async function savePlant(existing: PlantRow | null, data: PlantFormData): Promise<void> {
    loading.show();
    try {
      if (existing) {
        await updatePlant(existing.id, data);
        toast.success('Usina atualizada.');
      } else {
        const created = await createPlant(data);
        selectedPlantId = created.id;
        toast.success('Usina cadastrada.');
      }
    } catch {
      toast.error('Nao foi possivel salvar a usina.');
    } finally {
      loading.hide();
    }
  }

  async function confirmDeletePlant(plant: PlantRow): Promise<void> {
    const confirmed = window.confirm(`Excluir a usina ${plant.nome}? Essa acao nao pode ser desfeita.`);
    if (!confirmed) return;

    loading.show();
    try {
      await deletePlant(plant.id);
      toast.success('Usina excluida.');
      if (selectedPlantId === plant.id) selectedPlantId = null;
      await loadPlants();
    } catch {
      toast.error('Nao foi possivel excluir a usina.');
    } finally {
      loading.hide();
    }
  }
}

function createIdNameCell(idLabel: string, name: string): HTMLElement {
  const wrap = createElement('div', { className: 'cell-id-name' });
  wrap.append(
    createElement('span', { className: 'cell-id-tag', textContent: idLabel }),
    createElement('span', { textContent: name })
  );
  return wrap;
}

function createStatusDotLabel(label: string, tone: PlantStatusTone): HTMLElement {
  const wrap = createElement('span', { className: 'status-dot-label' });
  wrap.append(
    createElement('span', { className: `status-dot status-${tone}` }),
    createElement('span', { textContent: label })
  );
  return wrap;
}

function createOccupancyBar(percent: number): HTMLElement {
  const track = createElement('div', { className: 'occupancy-bar-track' });
  const fill = createElement('div', { className: 'occupancy-bar-fill' });
  fill.style.width = `${percent}%`;
  track.appendChild(fill);
  return track;
}

function createSummaryRow(label: string, value: string): HTMLElement {
  const row = createElement('div', { className: 'plant-summary-row' });
  row.append(createElement('span', { textContent: label }), createElement('strong', { textContent: value }));
  return row;
}

function plantLocationLabel(plant: PlantRow): string {
  if (plant.cidade && plant.uf) return `${plant.cidade}/${plant.uf}`;
  if (plant.cidade) return plant.cidade;
  return '-';
}

function normalize(value: string): string {
  return value
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '');
}
