import { createElement } from '../dom';
import { createIcon, type IconName } from './Icon';

export type DashboardMetric = {
  label: string;
  value: string;
  tone?: 'neutral' | 'success' | 'warning' | 'danger';
  // Opcionais -- so usados por quem quiser um card com icone e/ou clicavel
  // (ex.: cards de status na tela de Usinas funcionando como filtro).
  // Cliente/UC continuam passando so label/value/tone, sem nenhuma mudanca.
  icon?: IconName;
  active?: boolean;
  onClick?: () => void;
};

export function createDashboardCards(metrics: DashboardMetric[]): HTMLElement {
  const grid = createElement('section', { className: 'metric-grid' });

  metrics.forEach((metric) => {
    const classNames = ['metric-card', `metric-${metric.tone ?? 'neutral'}`];
    if (metric.icon) classNames.push('metric-card-icon');
    if (metric.onClick) classNames.push('metric-card-interactive');
    if (metric.active) classNames.push('active');

    const card: HTMLElement = metric.onClick
      ? createElement('button', { className: classNames.join(' '), type: 'button' })
      : createElement('article', { className: classNames.join(' ') });

    const value = createElement('strong', { textContent: metric.value });
    const label = createElement('span', { textContent: metric.label });

    if (metric.icon) {
      const chip = createElement('span', { className: 'metric-icon-chip' });
      chip.appendChild(createIcon(metric.icon));
      const text = createElement('span', { className: 'metric-text' });
      text.append(value, label);
      card.append(chip, text);
    } else {
      card.append(value, label);
    }

    if (metric.onClick) card.addEventListener('click', metric.onClick);
    grid.appendChild(card);
  });

  return grid;
}
