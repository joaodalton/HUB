import type { FilterKey } from '../types';
import { createElement } from '../dom';

const filters: Array<{ key: FilterKey; label: string }> = [
  { key: 'todos', label: 'Tudo' },
  { key: 'pastas', label: 'Clientes com pasta' },
  { key: 'imagens', label: 'Imagens em PDF' },
  { key: 'termo', label: 'Termo de adesao' }
];

type SearchPanelEvents = {
  onSearch: (term: string) => void;
  onFilterChange: (filter: FilterKey) => void;
};

export function createSearchPanel(events: SearchPanelEvents): HTMLElement {
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

  const hint = createElement('p', {
    className: 'search-hint',
    textContent: 'Pesquise, escolha os documentos e deixe tudo separado no painel ao lado.'
  });

  panel.append(label, row, filterRow, hint);
  return panel;
}
