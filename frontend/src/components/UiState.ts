import { createElement } from '../dom';

export type UiStateKind = 'empty' | 'filtered' | 'error';

type UiStateOptions = {
  kind: UiStateKind;
  title: string;
  description?: string;
  action?: { label: string; onClick: () => void };
  compact?: boolean;
};

const stateIcons: Record<UiStateKind, string> = {
  empty: '\u2014',
  filtered: '\u2315',
  error: '!'
};

export function createUiState({ kind, title, description, action, compact = false }: UiStateOptions): HTMLElement {
  const state = createElement('div', { className: `ui-state ui-state-${kind}${compact ? ' compact' : ''}` });
  state.setAttribute('role', kind === 'error' ? 'alert' : 'status');
  state.append(
    createElement('span', { className: 'ui-state-icon', textContent: stateIcons[kind] }),
    createElement('strong', { textContent: title })
  );
  if (description) state.appendChild(createElement('span', { textContent: description }));
  if (action) {
    const button = createElement('button', { className: 'secondary-button', type: 'button', textContent: action.label });
    button.addEventListener('click', action.onClick);
    state.appendChild(button);
  }
  return state;
}

export function createListSkeleton(rows = 4): HTMLElement {
  const list = createElement('div', { className: 'skeleton-list' });
  list.setAttribute('aria-label', 'Carregando lista');
  list.setAttribute('aria-busy', 'true');
  for (let index = 0; index < rows; index += 1) {
    const row = createElement('div', { className: 'skeleton-list-row' });
    row.append(createElement('span'), createElement('span'), createElement('span'));
    list.appendChild(row);
  }
  return list;
}

export function createTableSkeleton(columns: number, rows = 5): HTMLElement {
  const body = createElement('tbody', { className: 'skeleton-table-body' });
  body.setAttribute('aria-label', 'Carregando tabela');
  for (let rowIndex = 0; rowIndex < rows; rowIndex += 1) {
    const row = createElement('tr');
    for (let columnIndex = 0; columnIndex < columns; columnIndex += 1) {
      const cell = createElement('td');
      cell.appendChild(createElement('span', { className: 'skeleton-line' }));
      row.appendChild(cell);
    }
    body.appendChild(row);
  }
  return body;
}
