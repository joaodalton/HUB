// frontend/src/pages/PlantsPage.ts
import { createPlantCard, type PlantFormData } from '../components/PlantCard';
import { createImportacoesModal } from '../components/ImportacoesModal';
import { createPlantDistribuicaoModal, type PlantDistribuicaoModalUc } from '../components/PlantDistribuicaoModal';
import { createElement } from '../dom';
import { useGlobalLoading } from '../hooks/useGlobalLoading';
import { useToast } from '../hooks/useToast';
import { createBaseLayout } from '../layouts/BaseLayout';
import {
  createPlant,
  deletePlant,
  getPlants,
  removePlantConnection,
  type PlantRow,
  updatePlant
} from '../services/plantService';
import { getUcs, type UcRow } from '../services/ucsService';
import { readListParam, readPositiveListParam, writeListState } from '../services/listState';
import { renderPlantsListView, type PlantsListContext } from './plantsListView';
import { renderPlantDetailView } from './plantsDetailView';
import type { ConnectedUcRow } from './plantsShared';

export function createPlantsPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const toast = useToast();
  const loading = useGlobalLoading();
  let plants: PlantRow[] = [];
  let allUcs: UcRow[] = [];
  const requestedPlantId = Number(readListParam('selecionada'));
  let selectedPlantId: number | null = Number.isSafeInteger(requestedPlantId) && requestedPlantId > 0 ? requestedPlantId : null;
  let loadError = false;
  let isLoading = true;
  let searchTerm = readListParam('busca') ?? '';
  let statusFilter: string | null = readListParam('status') ?? null;
  let page = readPositiveListParam('pagina');

  const listContext: PlantsListContext = {
    getPlants: () => plants,
    getAllUcs: () => allUcs,
    isLoading: () => isLoading,
    loadError: () => loadError,
    getSearchTerm: () => searchTerm,
    setSearchTerm: (value) => { searchTerm = value; },
    getStatusFilter: () => statusFilter,
    setStatusFilter: (value) => { statusFilter = value; },
    getPage: () => page,
    setPage: (value) => { page = value; },
    clearSelection: () => { selectedPlantId = null; },
    onRetry: () => void loadPlants(),
    onSelectPlant: (plant) => {
      selectedPlantId = plant.id;
      writeListState({ selecionada: plant.id });
      renderContent();
    },
    onNewPlant: () => openPlantEditor(null),
    onImport: () => document.body.appendChild(createImportacoesModal(() => void loadPlants())),
    onEditPlant: (plant) => openPlantEditor(plant),
    onDeletePlant: (plant) => void confirmDeletePlant(plant)
  };

  const layout = createBaseLayout({
    content,
    eyebrow: 'Gestão',
    title: 'Usinas',
    description: 'Visualize geração, uso e status das usinas.'
  });

  renderContent();
  loadPlants();

  return layout;

  async function loadPlants(): Promise<void> {
    isLoading = true;
    loading.show();
    try {
      [plants, allUcs] = await Promise.all([getPlants(), getUcs()]);
      loadError = false;
    } catch {
      loadError = true;
      toast.error('Nao foi possivel carregar usinas. Verifique se o backend esta rodando.');
    } finally {
      isLoading = false;
      loading.hide();
      renderContent();
    }
  }

  function renderContent(): void {
    const selectedPlant = plants.find((item) => item.id === selectedPlantId) ?? null;
    content.replaceChildren(selectedPlant ? renderDetailView(selectedPlant) : renderPlantsListView(listContext));
  }

  function renderDetailView(plant: PlantRow): HTMLElement {
    return renderPlantDetailView({
      plant,
      allUcs,
      onBack: () => {
        selectedPlantId = null;
        writeListState({ selecionada: null }, 'replace');
        renderContent();
      },
      onEdit: (target) => openPlantEditor(target),
      onDelete: (target) => void confirmDeletePlant(target),
      onOpenDistribuicao: (target) => openDistribuicaoModal(target),
      onRemoveConnection: (target, row) => void confirmRemoveConnection(target, row)
    });
  }

  function openDistribuicaoModal(plant: PlantRow): void {
    const ucsForModal: PlantDistribuicaoModalUc[] = [];

    allUcs.forEach((uc) => {
      uc.conexoes
        .filter((conexao) => conexao.plantId === plant.id)
        .forEach((conexao) => {
          ucsForModal.push({
            ucId: uc.id,
            connectionId: conexao.id,
            codigo: uc.codigo || 'Sem codigo',
            clienteNome: uc.clienteNome ?? uc.apelido ?? 'Sem nome',
            consumo: uc.consumo,
            percentualAtual: Number(conexao.percentual) || 0
          });
        });
    });

    document.body.appendChild(createPlantDistribuicaoModal({
      plant,
      ucs: ucsForModal,
      onSaved: async () => {
        toast.success('Distribuição atualizada.');
        await loadPlants();
      },
      onError: (message) => toast.error(message)
    }));
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
