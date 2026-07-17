// frontend/src/pages/PlantsPage.ts
import { createDashboardCards } from '../components/DashboardCards';
import { createDataTable } from '../components/DataTable';
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

export function createPlantsPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const toast = useToast();
  const loading = useGlobalLoading();
  let plants: PlantRow[] = [];
  let selectedPlant: PlantRow | null = null;
  let isCreating = false;
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
      plants = await getPlants();
      loadError = false;
    } catch {
      loadError = true;
      toast.error('Nao foi possivel carregar usinas. Verifique se o backend esta rodando.');
    } finally {
      loading.hide();
      renderContent();
    }
  }

  function renderContent(): void {
    const pageActions = createElement('div', { className: 'page-actions' });
    const newPlantButton = createElement('button', { textContent: 'Nova usina', type: 'button' });
    const table = createDataTable<PlantRow>({
      title: 'Usinas cadastradas',
      eyebrow: 'Listagem',
      rows: plants,
      emptyMessage: loadError ? 'Nao foi possivel carregar usinas.' : 'Nenhuma usina cadastrada ainda.',
      onRowClick: (plant) => {
        selectedPlant = plant;
        isCreating = false;
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
    const blocks: HTMLElement[] = [createDashboardCards(getPlantMetrics(plants)), pageActions];

    newPlantButton.addEventListener('click', () => {
      selectedPlant = null;
      isCreating = true;
      renderContent();
    });

    pageActions.appendChild(newPlantButton);

    if (isCreating || selectedPlant) {
      blocks.push(createPlantEditor());
    }

    blocks.push(table);
    content.replaceChildren(...blocks);
  }

  function createPlantEditor(): HTMLElement {
    return createPlantCard({
      plant: selectedPlant ?? undefined,
      onCancel: () => {
        selectedPlant = null;
        isCreating = false;
        renderContent();
      },
      onSave: async (data) => {
        await savePlant(data);
        selectedPlant = null;
        isCreating = false;
        await loadPlants();
      },
      onDelete: selectedPlant ? async () => {
        const confirmed = window.confirm(`Excluir a usina ${selectedPlant?.nome}? Essa acao nao pode ser desfeita.`);
        if (!confirmed || !selectedPlant) return;

        loading.show();
        try {
          await deletePlant(selectedPlant.id);
          toast.success('Usina excluida.');
          selectedPlant = null;
          await loadPlants();
        } catch {
          toast.error('Nao foi possivel excluir a usina.');
        } finally {
          loading.hide();
        }
      } : undefined
    });
  }

  async function savePlant(data: PlantFormData): Promise<void> {
    loading.show();
    try {
      if (selectedPlant) {
        await updatePlant(selectedPlant.id, data);
        toast.success('Usina atualizada.');
      } else {
        await createPlant(data);
        toast.success('Usina cadastrada.');
      }
    } catch {
      toast.error('Nao foi possivel salvar a usina.');
    } finally {
      loading.hide();
    }
  }
}