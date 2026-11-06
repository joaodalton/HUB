// frontend/src/pages/plantsShared.ts
// Helpers e tipos compartilhados entre PlantsPage.ts, plantsListView.ts e
// plantsDetailView.ts -- extraidos de PlantsPage.ts (organizacao, sem
// mudanca de comportamento).
import { createElement } from '../dom';
import { createStatusBadge } from '../components/StatusBadge';
import type { PlantRow, PlantStatusTone } from '../services/plantService';
import type { UcRow } from '../services/ucsService';
import { t } from '../services/i18nService';

export type ConnectedUcRow = {
  id: number;
  connectionId: number;
  codigo: string;
  apelido: string;
  cliente: string;
  percentual: string;
  status: string;
};

// Abas sem backend ainda (Documentos de usina, Financeiro = V3.0, Historico e
// Logs nem tem model hoje) -- visiveis mas desabilitadas, mesmo padrao do
// ClientDetailView.ts. Funcao (nao const) pra ler o idioma atual a cada
// chamada, em vez de congelar a traducao no momento do import do modulo.
export function getUpcomingPlantTabs(): string[] {
  return [
    t('plants.upcomingTabs.documents'),
    t('plants.upcomingTabs.financial'),
    t('plants.upcomingTabs.history'),
    t('plants.upcomingTabs.logs')
  ];
}

export function connectedUcs(allUcs: UcRow[], plantId: number): ConnectedUcRow[] {
  const rows: ConnectedUcRow[] = [];

  allUcs.forEach((uc) => {
    uc.conexoes
      .filter((conexao) => conexao.plantId === plantId)
      .forEach((conexao) => {
        rows.push({
          id: uc.id,
          connectionId: conexao.id,
          codigo: uc.codigo || t('plants.connectedUcs.codeFallback'),
          apelido: uc.apelido || uc.clienteNome || t('plants.connectedUcs.nicknameFallback'),
          cliente: uc.clienteNome ?? '-',
          percentual: `${conexao.percentual}%`,
          status: t('plants.connectedUcs.statusActive')
        });
      });
  });

  return rows;
}

export function createIdNameCell(idLabel: string, name: string): HTMLElement {
  const wrap = createElement('div', { className: 'cell-id-name' });
  wrap.append(
    createElement('span', { className: 'cell-id-tag', textContent: idLabel }),
    createElement('span', { textContent: name })
  );
  return wrap;
}

export function createStatusDotLabel(label: string, tone: PlantStatusTone): HTMLElement {
  return createStatusBadge(label, tone);
}

export function createOccupancyBar(percent: number): HTMLElement {
  const track = createElement('div', { className: 'occupancy-bar-track' });
  const fill = createElement('div', { className: percent > 85 ? 'occupancy-bar-fill warning' : 'occupancy-bar-fill success' });
  fill.style.width = `${percent}%`;
  track.appendChild(fill);
  return track;
}

export function createMonthlyProductionChart(plant: PlantRow): HTMLElement {
  const values = Object.entries(plant.producaoMensal);
  if (!values.some(([, value]) => value > 0)) return createElement('span');

  const max = Math.max(...values.map(([, value]) => value), 1);
  const chart = createElement('section', { className: 'plant-production-chart' });
  const bars = createElement('div', { className: 'plant-production-bars' });
  values.forEach(([month, value]) => {
    const bar = createElement('span', { className: 'plant-production-bar', title: `${month}: ${formatValue(value)} kWh` });
    bar.style.height = `${Math.max(6, (value / max) * 100)}%`;
    const column = createElement('div', { className: 'plant-production-column' });
    column.append(bar, createElement('small', { textContent: month.slice(0, 3).toUpperCase() }));
    bars.appendChild(column);
  });
  chart.append(createElement('span', { className: 'eyebrow', textContent: t('plants.chart.monthlyGenerationEyebrow') }), bars);
  return chart;
}

export function createSummaryRow(label: string, value: string): HTMLElement {
  const row = createElement('div', { className: 'plant-summary-row' });
  row.append(createElement('span', { textContent: label }), createElement('strong', { textContent: value }));
  return row;
}

export function plantLocationLabel(plant: PlantRow): string {
  if (plant.cidade && plant.uf) return `${plant.cidade}/${plant.uf}`;
  if (plant.cidade) return plant.cidade;
  return '-';
}

export function formatValue(value: number): string {
  return new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 }).format(value);
}

export function normalize(value: string): string {
  return value
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '');
}
