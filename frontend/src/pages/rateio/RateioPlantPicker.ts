import { createIcon } from '../../components/Icon';
import { createElement } from '../../dom';
import type { PlantRow } from '../../services/plantService';
import { createStatusBadge, normalize } from './shared';
import { t } from '../../services/i18nService';

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
    createElement('span', { className: 'eyebrow', textContent: t('rateio.picker.eyebrow') }),
    createElement('h2', { textContent: t('rateio.picker.title') })
  );
  title.appendChild(titleText);

  const searchWrap = createElement('div', { className: 'page-actions' });
  const searchInput = createElement('input');
  searchInput.type = 'text';
  searchInput.placeholder = t('rateio.picker.searchPlaceholder');
  searchWrap.appendChild(searchInput);
  const listHolder = createElement('div', { className: 'rateio-plant-list' });

  function refreshList(): void {
    listHolder.replaceChildren();
    if (loadError) {
      listHolder.appendChild(createElement('p', { className: 'empty-state small', textContent: t('rateio.picker.loadError') }));
      return;
    }
    const filtered = plants.filter((plant) => normalize(plant.nome).includes(normalize(searchTerm)));
    if (!filtered.length) {
      listHolder.appendChild(createElement('p', {
        className: 'empty-state small',
        textContent: plants.length ? t('rateio.picker.emptySearch') : t('rateio.picker.emptyDefault')
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
      createElement('span', { textContent: `${plant.kwPico} kWp · ${connectedUcsCount(plant.id)} ${t('rateio.picker.connectedUcsSuffix')}` })
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
