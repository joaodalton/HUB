// frontend/src/pages/PlantsPage.ts
import { createDashboardCards } from '../components/DashboardCards';
import { createDataTable } from '../components/DataTable';
import { createDetailHeader } from '../components/DetailHeader';
import { createPlantCard, type PlantFormData } from '../components/PlantCard';
import { createElement } from '../dom';
import { useGlobalLoading } from '../hooks/useGlobalLoading';
import { useToast } from '../hooks/useToast';
import { createBaseLayout } from '../layouts/BaseLayout';
import {
  createPlant,
  deletePlant,
  getPlantMetrics,
  getPlants,
  type PlantRow,
  updatePlant
} from '../services/plantService';
import { getUcs, type UcRow } from '../services/ucsService';

type ConnectedUcRow = {
  id: number;
  uc: string;
  cliente: string;
  percentual: string;
  status: string;
};

export function createPlantsPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const toast = useToast();
  const loading = useGlobalLoading();
  let plants: PlantRow[] = [];
  let allUcs: UcRow[] = [];
  let selectedPlantId: number | null = null;
  let loadError = false;

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
            uc: uc.apelido ? `${uc.codigo} (${uc.apelido})` : uc.codigo,
            cliente: uc.clienteNome ?? '-',
            percentual: `${conexao.percentual}%`,
            status: 'Ativa'
          });
        });
    });

    return rows;
  }

  function renderContent(): void {
    const selectedPlant = plants.find((item) => item.id === selectedPlantId) ?? null;
    content.replaceChildren(selectedPlant ? renderDetailView(selectedPlant) : renderListView());
  }

  function renderListView(): HTMLElement {
    const fragment = createElement('div', { className: 'content-stack' });
    const pageActions = createElement('div', { className: 'page-actions' });
    const newPlantButton = createElement('button', { textContent: '+ Nova Usina', type: 'button' });
    const table = createDataTable<PlantRow>({
      title: 'Usinas cadastradas',
      eyebrow: 'Listagem',
      rows: plants,
      emptyMessage: loadError ? 'Nao foi possivel carregar usinas.' : 'Nenhuma usina cadastrada ainda.',
      onRowClick: (plant) => {
        selectedPlantId = plant.id;
        renderContent();
      },
      columns: [
        { key: 'nome', label: 'Nome' },
        { key: 'uc', label: 'UC' },
        { key: 'kwPico', label: 'kW pico', align: 'right' },
        { key: 'percentualDisponivel', label: 'Disponivel %', align: 'right' },
        { key: 'status', label: 'Status' }
      ]
    });

    newPlantButton.addEventListener('click', () => openPlantEditor(null));
    pageActions.appendChild(newPlantButton);

    fragment.append(createDashboardCards(getPlantMetrics(plants)), pageActions, table);
    return fragment;
  }

  function renderDetailView(plant: PlantRow): HTMLElement {
    const view = createElement('div', { className: 'detail-view' });
    const editButton = createElement('button', { className: 'secondary-button', textContent: 'Editar', type: 'button' });
    const deleteButton = createElement('button', { className: 'danger-button', textContent: 'Excluir', type: 'button' });

    editButton.addEventListener('click', () => openPlantEditor(plant));
    deleteButton.addEventListener('click', () => confirmDeletePlant(plant));

    const header = createDetailHeader({
      backLabel: 'Usinas',
      onBack: () => {
        selectedPlantId = null;
        renderContent();
      },
      title: plant.nome,
      badge: createStatusBadge(plant.status),
      actions: [editButton, deleteButton]
    });

    const info = createElement('div', { className: 'info-grid' });
    info.append(
      createInfoItem('UC da usina', plant.uc || '-'),
      createInfoItem('Potencia instalada', `${plant.kwPico} kWp`),
      createInfoItem('Marca do inversor', plant.marcaInversor || '-'),
      createInfoItem('Telefone do proprietario', plant.telefoneProprietario || '-'),
      createInfoItem('Email do proprietario', plant.emailProprietario || '-')
    );

    const connected = connectedUcs(plant.id);
    const occupied = Math.max(0, Math.min(100, 100 - plant.percentualDisponivel));

    const resumo = createDashboardCards([
      { label: 'UCs conectadas', value: String(connected.length) },
      { label: 'Disponivel para rateio', value: `${plant.percentualDisponivel}%`, tone: 'success' },
      { label: 'Geracao media', value: plant.mediaGeracao }
    ]);

    const occupancyWrap = createElement('div');
    occupancyWrap.append(
      createElement('div', { className: 'detail-section-title' }),
      createOccupancyBar(occupied)
    );
    occupancyWrap.querySelector('.detail-section-title')?.appendChild(
      createElement('h3', { textContent: `Ocupacao da usina — ${occupied}%` })
    );

    const ucSectionTitle = createElement('div', { className: 'detail-section-title' });
    ucSectionTitle.appendChild(createElement('h3', { textContent: `UCs conectadas (${connected.length})` }));

    const ucTable = createDataTable<ConnectedUcRow>({
      title: 'UCs conectadas',
      eyebrow: 'Rateio',
      rows: connected,
      emptyMessage: 'Nenhuma UC conectada a esta usina ainda.',
      columns: [
        { key: 'uc', label: 'UC' },
        { key: 'cliente', label: 'Cliente' },
        { key: 'percentual', label: '% Rateio', align: 'right' },
        { key: 'status', label: 'Status' }
      ]
    });

    view.append(header, info, resumo, occupancyWrap, ucSectionTitle, ucTable);
    return view;
  }

  function createOccupancyBar(percent: number): HTMLElement {
    const track = createElement('div', { className: 'occupancy-bar-track' });
    const fill = createElement('div', { className: 'occupancy-bar-fill' });
    fill.style.width = `${percent}%`;
    track.appendChild(fill);
    return track;
  }

  function createInfoItem(label: string, value: string): HTMLElement {
    const item = createElement('div', { className: 'info-item' });
    item.append(
      createElement('span', { className: 'info-label', textContent: label }),
      createElement('span', { className: 'info-value', textContent: value })
    );
    return item;
  }

  function createStatusBadge(status: string): HTMLElement {
    const normalized = status.toLowerCase();
    let tone = 'tone-warning';

    if (normalized.includes('online') || normalized.includes('ativ')) tone = 'tone-success';
    if (normalized.includes('inativ') || normalized.includes('vencid')) tone = 'tone-danger';

    return createElement('span', { className: `status-badge ${tone}`, textContent: status });
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