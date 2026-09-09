import { createElement } from '../../dom';
import { plantStatusLabel, plantStatusTone, type PlantStatusTone } from '../../services/plantService';

export function createStepHeader(stepNumber: number, title: string): HTMLElement {
  const header = createElement('div', { className: 'rateio-step-header' });
  header.append(
    createElement('span', { className: 'rateio-step-badge', textContent: String(stepNumber) }),
    createElement('h2', { textContent: title })
  );
  return header;
}

export function createFunilStat(label: string, value: number | string): HTMLElement {
  const card = createElement('article', { className: 'rateio-funil-stat' });
  card.append(
    createElement('span', { className: 'rateio-funil-stat-label', textContent: label }),
    createElement('strong', { className: 'rateio-funil-stat-value', textContent: String(value) })
  );
  return card;
}

export function createStatusBadge(status: string): HTMLElement {
  const tone: PlantStatusTone = plantStatusTone(status);
  return createElement('span', {
    className: tone === 'neutral' ? 'status-badge' : `status-badge tone-${tone}`,
    textContent: plantStatusLabel(status)
  });
}

export function formatNumber(value: number): string {
  return value.toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
}

export function round2(value: number): number {
  return Math.round(value * 100) / 100;
}

export function normalize(value: string): string {
  return value
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '');
}

export function defaultCompetencia(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
}
