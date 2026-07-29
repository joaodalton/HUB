import type { FilterKey } from '../types';
import { createElement } from '../dom';

const filters: Array<{ key: FilterKey; label: string }> = [
  { key: 'todos', label: 'Tudo' },
  { key: 'pastas', label: 'Clientes com pasta' },
  { key: 'imagens', label: 'Imagens em PDF' },
  { key: 'termo', label: 'Termo de adesao' }
];

export type SearchPanelEvents = {
  onSearch: (term: string) => void;
  onFilterChange: (filter: FilterKey) => void;
  onTypeChange: (tipo: string) => void;
  onDateRangeChange: (from: string, to: string) => void;
};

export function createSearchPanel(events: SearchPanelEvents): {
  element: HTMLElement;
  updateTypeOptions: (types: string[]) => void;
} {
  const panel = createElement('section', { className: 'search-panel' });

  const label = createElement('label', { className: 'search-label', textContent: 'Buscar' });
  label.htmlFor = 'busca';

  const row = createElement('div', { className: 'search-row' });
  const input = createElement('input');
  input.id = 'busca';
  input.type = 'text';
  input.placeholder = 'cliente, termo, imagem ou pasta...';
  input.autocomplete = 'off';

  const button = createElement('button', { textContent: 'Buscar', type: 'button' });

  const runSearch = () => events.onSearch(input.value.trim());
  button.addEventListener('click', runSearch);
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') runSearch();
  });

  row.append(input, button);

  const filterRow = createElement('div', { className: 'filter-row' });
  filterRow.setAttribute('aria-label', 'Filtros de busca');

  filters.forEach(({ key, label: filterLabel }) => {
    const chip = createElement('button', {
      className: key === 'todos' ? 'filter-chip active' : 'filter-chip',
      textContent: filterLabel,
      type: 'button'
    });

    chip.addEventListener('click', () => {
      filterRow.querySelectorAll('.filter-chip').forEach((item) => item.classList.remove('active'));
      chip.classList.add('active');
      events.onFilterChange(key);
    });

    filterRow.appendChild(chip);
  });

  // Filtro dinamico: as opcoes de "Tipo" nao sao uma lista fixa no codigo -- sao
  // montadas a partir dos tipos que a busca atual realmente trouxe, via updateTypeOptions().
  const refineRow = createElement('div', { className: 'refine-row' });

  const typeField = createElement('label', { className: 'form-field' });
  const typeLabel = createElement('span', { textContent: 'Tipo de arquivo' });
  const typeSelect = createElement('select');

  const dateFromField = createElement('label', { className: 'form-field' });
  const dateFromLabel = createElement('span', { textContent: 'De' });
  const dateFrom = createElement('input');
  dateFrom.type = 'date';

  const dateToField = createElement('label', { className: 'form-field' });
  const dateToLabel = createElement('span', { textContent: 'Ate' });
  const dateTo = createElement('input');
  dateTo.type = 'date';

  typeSelect.addEventListener('change', () => events.onTypeChange(typeSelect.value));
  dateFrom.addEventListener('change', () => events.onDateRangeChange(dateFrom.value, dateTo.value));
  dateTo.addEventListener('change', () => events.onDateRangeChange(dateFrom.value, dateTo.value));

  typeField.append(typeLabel, typeSelect);
  dateFromField.append(dateFromLabel, dateFrom);
  dateToField.append(dateToLabel, dateTo);
  refineRow.append(typeField, dateFromField, dateToField);

  const hint = createElement('p', {
    className: 'search-hint',
    textContent: 'Pesquise, escolha os documentos e deixe tudo separado no painel ao lado.'
  });

  panel.append(label, row, filterRow, refineRow, hint);

  function updateTypeOptions(types: string[]): void {
    const previousValue = typeSelect.value;
    typeSelect.replaceChildren();

    const allOption = createElement('option', { textContent: 'Todos os tipos' });
    allOption.value = 'todos';
    typeSelect.appendChild(allOption);

    types.forEach((type) => {
      const option = createElement('option', { textContent: type });
      option.value = type;
      typeSelect.appendChild(option);
    });

    typeSelect.value = types.includes(previousValue) ? previousValue : 'todos';
  }

  return { element: panel, updateTypeOptions };
}