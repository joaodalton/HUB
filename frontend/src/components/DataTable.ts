import { createElement, statusTone } from '../dom';

export type TableColumn<T> = {
  key: string;
  label: string;
  align?: 'left' | 'right';
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
  onRowClick?: (row: T) => void;
};

export function createDataTable<T extends Record<string, unknown>>({
  title,
  eyebrow,
  rows,
  columns,
  emptyMessage,
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
  const headerRow = createElement('tr');

  columns.forEach((column) => {
    const th = createElement('th', { textContent: column.label });
    if (column.align === 'right') th.classList.add('align-right');
    headerRow.appendChild(th);
  });

  thead.appendChild(headerRow);

  if (rows.length === 0) {
    const row = createElement('tr');
    const cell = createElement('td', { className: 'empty-table', textContent: emptyMessage });
    cell.colSpan = columns.length;
    row.appendChild(cell);
    tbody.appendChild(row);
  } else {
    rows.forEach((item) => {
      const row = createElement('tr');
      if (onRowClick) {
        row.classList.add('clickable-row');
        row.addEventListener('click', () => onRowClick(item));
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
          cell.textContent = value;
          if (column.key === 'status') cell.appendChild(createStatusMark(value));
        }

        row.appendChild(cell);
      });

      tbody.appendChild(row);
    });
  }

  titleText.append(eyebrowElement, heading);
  panelTitle.appendChild(titleText);
  table.append(thead, tbody);
  tableWrap.appendChild(table);
  panel.append(panelTitle, tableWrap);

  return panel;
}

function createStatusMark(status: string): HTMLElement {
  return createElement('span', { className: `status-dot status-${statusTone(status)}` });
}
