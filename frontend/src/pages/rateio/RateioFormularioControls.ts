import { createIcon } from '../../components/Icon';
import { createElement } from '../../dom';
import type { FormularioLinha } from '../../services/rateioFormularioService';

export function createEditableTable<T extends { ordem: number }>({ columns, rows, emptyMessage, getRowKey, onChange }: {
  columns: Array<{ key: keyof T; label: string; align?: 'right'; render?: (row: T) => string; editable?: boolean; onChange?: (row: T, value: string) => void }>;
  rows: T[];
  emptyMessage?: string;
  getRowKey: (row: T) => number | string;
  onChange?: (row: T, value: string) => void;
}): HTMLElement {
  const table = createElement('div', { className: 'rateio-table' });
  const header = createElement('div', { className: 'rateio-table-header' });
  columns.forEach((column) => header.appendChild(createElement('div', {
    className: `rateio-table-cell ${column.align === 'right' ? 'right' : ''}`, textContent: column.label
  })));
  table.appendChild(header);
  if (!rows.length) {
    table.appendChild(createElement('p', { className: 'empty-state small', textContent: emptyMessage ?? 'Nenhum registro.' }));
    return table;
  }
  rows.forEach((row) => {
    const tr = createElement('div', { className: 'rateio-table-row' });
    tr.dataset.rowKey = String(getRowKey(row));
    columns.forEach((column) => {
      const cell = createElement('div', { className: `rateio-table-cell ${column.align === 'right' ? 'right' : ''}` });
      cell.textContent = column.render ? column.render(row) : String(row[column.key] ?? '');
      const update = column.onChange;
      if (column.editable && update) {
        const input = createElement('input'); input.type = 'text'; input.value = String(row[column.key] ?? '');
        input.addEventListener('change', () => { update(row, input.value); onChange?.(row, input.value); });
        cell.replaceChildren(input);
      }
      tr.appendChild(cell);
    });
    table.appendChild(tr);
  });
  return table;
}

export function createResponsavelField(label: string, value: string, onChange: (value: string) => void): HTMLElement {
  const field = createElement('div', { className: 'rateio-form-field' });
  const input = createElement('input'); input.type = 'text'; input.value = value;
  input.addEventListener('input', () => onChange(input.value));
  field.append(createElement('label', { className: 'settings-subheading', textContent: label }), input);
  return field;
}

export function createTermoAdesaoBadge(row: FormularioLinha): HTMLElement {
  const badge = createElement('span', { className: 'termo-badge' });
  if (row.termoAdesaoOk) {
    badge.append(createIcon('check'), document.createTextNode('OK')); badge.classList.add('ok');
  } else {
    badge.append(createIcon('pending'), document.createTextNode('Faltando')); badge.classList.add('falta');
  }
  return badge;
}

export function createFormularioStat(label: string, value: string): HTMLElement {
  const stat = createElement('div', { className: 'rateio-funil-stat' });
  stat.append(createElement('span', { className: 'rateio-funil-stat-label', textContent: label }), createElement('strong', { className: 'rateio-funil-stat-value', textContent: value }));
  return stat;
}

export function createFormularioCheck(label: string, ok: boolean, pendingLabel?: string): HTMLElement {
  return createElement('span', {
    className: ok ? 'status-badge tone-success' : pendingLabel ? 'status-badge tone-warning' : 'status-badge tone-danger',
    textContent: pendingLabel ?? label
  });
}
