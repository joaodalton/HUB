import { createElement } from '../dom';

export type StatusTone = 'neutral' | 'success' | 'warning' | 'danger' | 'info';

const toneIcons: Record<StatusTone, string> = {
  neutral: '\u2022',
  success: '\u2713',
  warning: '!',
  danger: '\u00d7',
  info: 'i'
};

export function createStatusBadge(label: string, tone: StatusTone = 'neutral'): HTMLElement {
  const badge = createElement('span', {
    className: tone === 'neutral' ? 'status-badge' : `status-badge tone-${tone}`
  });
  badge.setAttribute('aria-label', label);
  badge.append(
    createElement('span', { className: 'status-badge-icon', textContent: toneIcons[tone] }),
    createElement('span', { textContent: label })
  );
  return badge;
}
