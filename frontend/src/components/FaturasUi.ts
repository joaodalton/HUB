import { createElement } from '../dom';
import type { FaturaRow } from '../services/faturasService';

export function createModal(title: string, eyebrow: string): HTMLElement {
  const overlay = createElement('section', { className: 'modal-overlay' });
  const card = createElement('article', { className: 'plant-card fatura-modal' });
  const header = createElement('div', { className: 'modal-header' });
  const heading = createElement('div');
  heading.append(createElement('span', { className: 'eyebrow', textContent: eyebrow }), createElement('h2', { textContent: title }));
  const close = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Fechar' });
  close.addEventListener('click', () => overlay.remove());
  header.append(heading, close);
  card.append(header, createElement('div', { className: 'modal-body' }));
  overlay.appendChild(card);
  overlay.addEventListener('click', (event) => { if (event.target === overlay) overlay.remove(); });
  document.body.appendChild(overlay);
  return overlay;
}

export function detailSection(title: string, fields: Array<[string, string]>): HTMLElement {
  const section = createElement('section', { className: 'fatura-detail-section' });
  section.appendChild(createElement('h3', { textContent: title }));
  const grid = createElement('div', { className: 'detail-info-grid' });
  fields.forEach(([label, value]) => {
    const field = createElement('div', { className: 'detail-info-field' });
    field.append(createElement('span', { textContent: label }), createElement('strong', { textContent: value }));
    grid.appendChild(field);
  });
  section.appendChild(grid);
  return section;
}
export function selectField(label: string, options: Array<{ value: string; label: string }>, required = false) {
  const field = createElement('label', { className: 'form-field' });
  const select = createElement('select'); select.required = required;
  select.append(...options.map((item) => option(item.value, item.label)));
  field.append(createElement('span', { textContent: label }), select);
  return { field, select };
}
export function textField(label: string, type: string, value: string, required = false) {
  const field = createElement('label', { className: 'form-field' });
  const input = createElement('input'); input.type = type; input.value = value; input.required = required;
  field.append(createElement('span', { textContent: label }), input);
  return { field, input };
}
export function option(value: string, label: string): HTMLOptionElement { const element = createElement('option', { textContent: label }); element.value = value; return element; }
export function filterSelect(label: string, value: string, options: Array<{ value: string; label: string }>, onChange: (value: string) => void): HTMLElement {
  const field = createElement('label', { className: 'faturas-filter-field' });
  const select = createElement('select'); select.append(...options.map((item) => option(item.value, item.label))); select.value = value;
  select.addEventListener('change', () => onChange(select.value));
  field.append(createElement('span', { textContent: label }), select); return field;
}
export function createBadge(label: string, tone: 'warning' | 'success' | 'danger' | 'neutral' = 'neutral'): HTMLElement {
  return createElement('span', { className: tone === 'neutral' ? 'status-badge' : `status-badge tone-${tone}`, textContent: label });
}
export function createChargeCell(charges: Array<{ asaasId: string | null; asaasStatus: FaturaRow['asaasStatus']; statusInterno: string | null }>): HTMLElement {
  if (!charges.length) return createBadge('Sem cobrança');
  const wrap = createElement('div', { className: 'fatura-charge-cell' });
  charges.forEach((charge) => wrap.appendChild(createBadge(charge.asaasId ? statusLabel(charge.asaasStatus) : charge.statusInterno ?? 'Aguardando emissão', charge.asaasStatus === 'received' && charge.asaasId ? 'success' : charge.asaasStatus === 'overdue' && charge.asaasId ? 'danger' : 'warning')));
  return wrap;
}
export function statusLabel(status: FaturaRow['asaasStatus']): string { return ({ pending: 'Pendente', received: 'Recebida', overdue: 'Vencida', canceled: 'Cancelada', refunded: 'Estornada' })[status]; }
export function formatCurrency(value: string | number | null | undefined): string { return value == null ? '—' : new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(Number(value)); }
export function formatDate(value: string | null | undefined): string { return value ? new Date(`${value.slice(0, 10)}T12:00:00`).toLocaleDateString('pt-BR') : '—'; }
export function formatReference(value: string | null): string { if (!value) return '—'; if (!/^\d{4}-\d{2}$/.test(value)) return value; const [year, month] = value.split('-'); return `${month}/${year}`; }
export function currentMonth(): string { const now = new Date(); return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`; }
