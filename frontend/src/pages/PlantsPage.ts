import { createDashboardCards } from '../components/DashboardCards';
import { createDataTable } from '../components/DataTable';
import { createElement } from '../dom';
import { createBaseLayout } from '../layouts/BaseLayout';
import { getPlantMetrics, getPlants, type PlantRow } from '../services/operationsService';

export function createPlantsPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const table = createDataTable<PlantRow>({
    title: 'Usinas cadastradas',
    eyebrow: 'Listagem',
    rows: getPlants(),
    emptyMessage: 'Nenhuma usina cadastrada ainda.',
    columns: [
      { key: 'nome', label: 'Nome' },
      { key: 'uc', label: 'UC' },
      { key: 'mediaGeracao', label: 'M. geracao', align: 'right' },
      { key: 'status', label: 'Status' }
    ]
  });

  content.append(createDashboardCards(getPlantMetrics()), table);

  return createBaseLayout({
    content,
    eyebrow: 'Usinas',
    title: 'Visualize geracao, uso e status das usinas'
  });
}
