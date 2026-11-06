// frontend/src/pages/ucsShared.ts
// Helpers compartilhados extraidos de UcsPage.ts (organizacao, sem mudanca
// de comportamento).
import { createElement } from '../dom';
import { t } from '../services/i18nService';

export function createListPagination(page: number, pages: number, total: number, onPage: (page: number) => void): HTMLElement {
  const nav = createElement('nav', { className: 'faturas-pagination pagination-left' });
  const previous = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('ucs.pagination.previous') });
  previous.disabled = page <= 1;
  previous.addEventListener('click', () => onPage(page - 1));
  const next = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('ucs.pagination.next') });
  next.disabled = page >= pages || total === 0;
  next.addEventListener('click', () => onPage(page + 1));
  nav.append(previous, createElement('span', { textContent: `${total ? page : 0} ${t('ucs.pagination.of')} ${total ? pages : 0}` }), next);
  return nav;
}

// Split-based, sem Date() -- mesmo motivo documentado em ClientDetailView.ts (evita o bug de "um dia antes" por causa de fuso horario).
export function formatUcDate(value: string | null): string {
  if (!value) return t('ucs.notInformed');
  const [year, month, day] = value.split('-');
  return `${day}/${month}/${year}`;
}

export function isContractExpiring(value: string | null): boolean {
  if (!value) return false;
  const [year, month, day] = value.split('-').map(Number);
  const end = new Date(year, month - 1, day);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const deadline = new Date(today);
  deadline.setDate(deadline.getDate() + 30);
  return end >= today && end <= deadline;
}
