import { createDashboardCards } from '../components/DashboardCards';
import { createDataTable } from '../components/DataTable';
import { createPlantCard, type PlantFormData } from '../components/PlantCard';
import { createElement } from '../dom';
import { useToast } from '../hooks/useToast';
import { createBaseLayout } from '../layouts/BaseLayout';
import {
  createPlant,
  deletePlant,
  getPlantMetrics,
  getPlants,
  type PlantRow,
  updatePlant
} from '../services/operationsService';

export function createPlantsPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const toast = useToast();
  let selectedPlant: PlantRow | null = null;
  let isCreating = false;

  renderContent();

  return createBaseLayout({
    content,
    eyebrow: 'Usinas',
    title: 'Visualize geracao, uso e status das usinas'
  });

  function renderContent(): void {
    const pageActions = createElement('div', { className: 'page-actions' });
    const newPlantButton = createElement('button', { textContent: 'Nova usina', type: 'button' });
    const table = createDataTable<PlantRow>({
      title: 'Usinas cadastradas',
      eyebrow: 'Listagem',
      rows: getPlants(),
      emptyMessage: 'Nenhuma usina cadastrada ainda.',
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
    const blocks: HTMLElement[] = [createDashboardCards(getPlantMetrics()), pageActions];

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
      onSave: (data) => {
        savePlant(data);
        selectedPlant = null;
        isCreating = false;
        renderContent();
      },
      onDelete: selectedPlant ? () => {
        const confirmed = window.confirm(`Excluir a usina ${selectedPlant?.nome}? Essa acao nao pode ser desfeita.`);

        if (!confirmed || !selectedPlant) return;

        deletePlant(selectedPlant.id);
        toast.success('Usina excluida.');
        selectedPlant = null;
        renderContent();
      } : undefined
    });
  }

  function savePlant(data: PlantFormData): void {
    if (selectedPlant) {
      updatePlant(selectedPlant.id, data);
      toast.success('Usina atualizada.');
      return;
    }

    createPlant(data);
    toast.success('Usina cadastrada.');
  }
}
