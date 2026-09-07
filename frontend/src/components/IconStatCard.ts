import { createElement } from '../dom';
import { createIcon, type IconName } from './Icon';

export type IconStatCardProps = {
  icon: IconName;
  chipColor: 'blue' | 'green' | 'amber' | 'red' | 'purple';
  value: string;
  label: string;
  trend?: string;
  onClick?: () => void;
};

export function createIconStatCard({ icon, chipColor, value, label, trend, onClick }: IconStatCardProps): HTMLElement {
  const card: HTMLElement = onClick
    ? createElement('button', { className: 'icon-stat-card icon-stat-card-interactive', type: 'button' })
    : createElement('article', { className: 'icon-stat-card' });
  const chip = createElement('span', { className: `icon-stat-chip icon-stat-chip-${chipColor}` });
  const content = createElement('span', { className: 'icon-stat-content' });

  chip.appendChild(createIcon(icon));
  content.append(
    createElement('strong', { textContent: value }),
    createElement('span', { className: 'icon-stat-label', textContent: label }),
  );
  if (trend) content.appendChild(createElement('span', { className: 'icon-stat-trend', textContent: trend }));
  if (onClick) card.addEventListener('click', onClick);

  card.append(chip, content);
  return card;
}
