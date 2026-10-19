import { createElement, statusTone } from '../dom';
import { createStatusBadge } from './StatusBadge';
import { createTableSkeleton, createUiState, type UiStateKind } from './UiState';

export type TableColumn<T> = {
  key: string;
  label: string;
  align?: 'left' | 'right';
  headerRender?: () => HTMLElement;
  // Opcional: quando presente, ignora item[key] e desenha a celula do jeito
  // que a pagina quiser (ex.: id+nome numa celula so, botao de acao). key
  // continua obrigatorio (serve so de identificador da coluna nesse caso).
  render?: (row: T) => HTMLElement | string;
};

type DataTableOptions<T> = {
  title: string;
  eyebrow: string;
  rows: T[];
  columns: Array<TableColumn<T>>;
  emptyMessage: string;
  state?: 'ready' | 'loading' | UiStateKind;
  stateTitle?: string;
  emptyAction?: { label: string; onClick: () => void };
  errorAction?: { label: string; onClick: () => void };
  onRowClick?: (row: T) => void;
};

export function createDataTable<T extends Record<string, unknown>>({
  title,
  eyebrow,
  rows,
  columns,
  emptyMessage,
  state = 'ready',
  stateTitle,
  emptyAction,
  errorAction,
  onRowClick
}: DataTableOptions<T>): HTMLElement {
  const panel = createElement('section', { className: 'data-panel data-panel-scroll' });
  const panelTitle = createElement('div', { className: 'panel-title' });
  const titleText = createElement('div');
  const eyebrowElement = createElement('span', { className: 'eyebrow', textContent: eyebrow });
  const heading = createElement('h2', { textContent: title });
  const tableWrap = createElement('div', { className: 'table-wrap' });
  const table = createElement('table', { className: 'data-table' });
  const thead = createElement('thead');
  const tbody = createElement('tbody');
  let renderedBody: HTMLElement = tbody;
  const headerRow = createElement('tr');

  columns.forEach((column) => {
    const th = createElement('th');
    if (column.headerRender) th.appendChild(column.headerRender());
    else th.textContent = column.label;
    if (column.align === 'right') th.classList.add('align-right');
    headerRow.appendChild(th);
  });

  thead.appendChild(headerRow);

  if (state === 'loading') {
    renderedBody = createTableSkeleton(columns.length);
  } else if (rows.length === 0) {
    const row = createElement('tr');
    const cell = createElement('td', { className: 'empty-table' });
    cell.colSpan = columns.length;
    const kind = state === 'ready' ? 'empty' : state;
    cell.appendChild(createUiState({
      kind,
      title: stateTitle ?? emptyMessage,
      action: state === 'filtered' ? emptyAction : state === 'error' ? errorAction : undefined,
      compact: true
    }));
    row.appendChild(cell);
    tbody.appendChild(row);
  } else {
    rows.forEach((item) => {
      const row = createElement('tr');
      if (onRowClick) {
        row.classList.add('clickable-row');
        row.tabIndex = 0;
        row.setAttribute('role', 'button');
        row.addEventListener('click', () => onRowClick(item));
        row.addEventListener('keydown', (event) => {
          if (event.key !== 'Enter' && event.key !== ' ') return;
          event.preventDefault();
          onRowClick(item);
        });
      }

      columns.forEach((column) => {
        const cell = createElement('td');
        if (column.align === 'right') cell.classList.add('align-right');

        if (column.render) {
          const rendered = column.render(item);
          if (typeof rendered === 'string') cell.textContent = rendered;
          else cell.appendChild(rendered);
        } else {
          const value = String(item[column.key] ?? '');
          if (column.key === 'status') cell.appendChild(createStatusBadge(value, statusTone(value)));
          else cell.textContent = value;
        }

        row.appendChild(cell);
      });

      tbody.appendChild(row);
    });
  }

  titleText.append(eyebrowElement, heading);
  panelTitle.appendChild(titleText);
  table.append(thead, renderedBody);
  tableWrap.appendChild(table);
  panel.append(panelTitle, tableWrap);

  return panel;
}
