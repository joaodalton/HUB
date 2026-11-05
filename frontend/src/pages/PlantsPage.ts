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
import { t } from '../services/i18nService';
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
    eyebrow: t('plants.page.eyebrow'),
    title: t('plants.page.title'),
    description: t('plants.page.description')
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
      toast.error(t('plants.toast.loadError'));
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
            codigo: uc.codigo || t('plants.connectedUcs.codeFallback'),
            clienteNome: uc.clienteNome ?? uc.apelido ?? t('plants.distribuicao.clientNameFallback'),
            consumo: uc.consumo,
            percentualAtual: Number(conexao.percentual) || 0
          });
        });
    });

    document.body.appendChild(createPlantDistribuicaoModal({
      plant,
      ucs: ucsForModal,
      onSaved: async () => {
        toast.success(t('plants.toast.distribuicaoUpdated'));
        await loadPlants();
      },
      onError: (message) => toast.error(message)
    }));
  }

  async function confirmRemoveConnection(plant: PlantRow, row: ConnectedUcRow): Promise<void> {
    const confirmed = window.confirm(`${t('plants.confirmRemoveConnection.prefix')} ${row.codigo}${t('plants.confirmRemoveConnection.suffix')}`);
    if (!confirmed) return;

    loading.show();
    try {
      await removePlantConnection(plant.id, row.connectionId);
      toast.success(t('plants.toast.connectionRemoved'));
      await loadPlants();
    } catch {
      toast.error(t('plants.toast.connectionRemoveError'));
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
        toast.success(t('plants.toast.updated'));
      } else {
        const created = await createPlant(data);
        selectedPlantId = created.id;
        toast.success(t('plants.toast.created'));
      }
    } catch {
      toast.error(t('plants.toast.saveError'));
    } finally {
      loading.hide();
    }
  }

  async function confirmDeletePlant(plant: PlantRow): Promise<void> {
    const confirmed = window.confirm(`${t('plants.confirmDelete.prefix')} ${plant.nome}${t('plants.confirmDelete.suffix')}`);
    if (!confirmed) return;

    loading.show();
    try {
      await deletePlant(plant.id);
      toast.success(t('plants.toast.deleted'));
      if (selectedPlantId === plant.id) selectedPlantId = null;
      await loadPlants();
    } catch {
      toast.error(t('plants.toast.deleteError'));
    } finally {
      loading.hide();
    }
  }
}
