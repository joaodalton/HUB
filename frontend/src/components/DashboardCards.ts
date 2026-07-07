import { createElement } from '../dom';

export type DashboardMetric = {
  label: string;
  value: string;
  tone?: 'neutral' | 'success' | 'warning';
};

export function createDashboardCards(metrics: DashboardMetric[]): HTMLElement {
  const grid = createElement('section', { className: 'metric-grid' });

  metrics.forEach((metric) => {
    const card = createElement('article', {
      className: `metric-card metric-${metric.tone ?? 'neutral'}`
    });
    const value = createElement('strong', { textContent: metric.value });
    const label = createElement('span', { textContent: metric.label });

    card.append(value, label);
    grid.appendChild(card);
  });

  return grid;
}
