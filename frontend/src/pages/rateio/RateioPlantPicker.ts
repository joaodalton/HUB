import { createIcon } from '../../components/Icon';
import { createElement } from '../../dom';
import type { PlantRow } from '../../services/plantService';
import { createStatusBadge, normalize } from './shared';

type Props = {
  plants: PlantRow[];
  loadError: boolean;
  selectedPlantId: number | null;
  connectedUcsCount: (plantId: number) => number;
  onSelect: (plant: PlantRow) => void;
};

export function renderRateioPlantPicker({ plants, loadError, selectedPlantId, connectedUcsCount, onSelect }: Props): HTMLElement {
  let searchTerm = '';
  const panel = createElement('section', { className: 'data-panel rateio-picker' });
  const title = createElement('div', { className: 'panel-title' });
  const titleText = createElement('div');
  titleText.append(
    createElement('span', { className: 'eyebrow', textContent: 'Escolha' }),
    createElement('h2', { textContent: 'Selecione a usina para iniciar o rateio' })
  );
  title.appendChild(titleText);

  const searchWrap = createElement('div', { className: 'page-actions' });
  const searchInput = createElement('input');
  searchInput.type = 'text';
  searchInput.placeholder = 'Pesquisar por nome...';
  searchWrap.appendChild(searchInput);
  const listHolder = createElement('div', { className: 'rateio-plant-list' });

  function refreshList(): void {
    listHolder.replaceChildren();
    if (loadError) {
      listHolder.appendChild(createElement('p', { className: 'empty-state small', textContent: 'Nao foi possivel carregar usinas.' }));
      return;
    }
    const filtered = plants.filter((plant) => normalize(plant.nome).includes(normalize(searchTerm)));
    if (!filtered.length) {
      listHolder.appendChild(createElement('p', {
        className: 'empty-state small',
        textContent: plants.length ? 'Nenhuma usina encontrada para essa busca.' : 'Nenhuma usina cadastrada ainda.'
      }));
      return;
    }
    filtered.forEach((plant) => listHolder.appendChild(createPlantPickRow(plant)));
  }

  function createPlantPickRow(plant: PlantRow): HTMLElement {
    const row = createElement('button', {
      className: plant.id === selectedPlantId ? 'rateio-plant-row active' : 'rateio-plant-row',
      type: 'button'
    });
    const iconChip = createElement('span', { className: 'rateio-plant-icon' });
    iconChip.appendChild(createIcon('plants'));
    const info = createElement('div', { className: 'rateio-plant-row-info' });
    info.append(
      createElement('strong', { textContent: plant.nome }),
      createElement('span', { textContent: `${plant.kwPico} kWp · ${connectedUcsCount(plant.id)} UCs conectadas` })
    );
    row.append(iconChip, info, createStatusBadge(plant.status));
    row.addEventListener('click', () => onSelect(plant));
    return row;
  }

  searchInput.addEventListener('input', () => {
    searchTerm = searchInput.value;
    refreshList();
  });
  refreshList();
  panel.append(title, searchWrap, listHolder);
  return panel;
}
