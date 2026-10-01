import { createElement } from '../dom';
import { createDataTable } from '../components/DataTable';
import { createDetailDrawer } from '../components/DetailDrawer';
import { createIconStatCard, type IconStatCardProps } from '../components/IconStatCard';
import { formattedLogDate, type LogRow } from '../services/logsService';
import { createPanelHeader } from './settingsShared';

// ---------- Home ----------

export function createHomePanel(
  logs: LogRow[],
  logsLoaded: boolean,
  onSeeAllLogs: () => void
): HTMLElement {
  const logsCard = createElement('section', { className: 'settings-panel' });
  const seeAllButton = createElement('button', { className: 'secondary-link', textContent: 'Ver todos', type: 'button' });
  seeAllButton.addEventListener('click', onSeeAllLogs);
  logsCard.appendChild(createPanelHeader('Logs recentes', 'Últimos eventos do sistema', seeAllButton));

  if (!logsLoaded) {
    logsCard.appendChild(createElement('p', { className: 'settings-hint', textContent: 'Carregando logs...' }));
  } else if (logs.length === 0) {
    logsCard.appendChild(createElement('p', { className: 'settings-hint', textContent: 'Nenhum log registrado ainda.' }));
  } else {
    const list = createElement('div', { className: 'log-list' });
    logs.slice(0, 5).forEach((log) => list.appendChild(createLogRow(log)));
    logsCard.appendChild(list);
  }

  return logsCard;
}

function createLogRow(log: LogRow): HTMLElement {
  const row = createElement('div', { className: 'log-row' });
  row.append(
    createElement('span', { className: `log-level log-level-${log.nivel}`, textContent: log.nivel }),
    createElement('span', { className: 'log-message', textContent: log.mensagem || log.acao }),
    createElement('span', { className: 'log-meta', textContent: formattedLogDate(log) })
  );
  return row;
}

// ---------- Logs ----------

export function createLogsPanel(logs: LogRow[], loaded: boolean): HTMLElement {
  const stack = createElement('section', { className: 'content-stack' });
  const metrics: IconStatCardProps[] = [
    { label: 'Informações', value: String(logs.filter((log) => log.nivel === 'info').length), chipColor: 'blue', icon: 'dashboard' },
    { label: 'Alertas', value: String(logs.filter((log) => log.nivel === 'warning').length), chipColor: 'amber', icon: 'pending' },
    { label: 'Erros', value: String(logs.filter((log) => log.nivel === 'error').length), chipColor: 'red', icon: 'x' }
  ];
  const cards = createElement('section', { className: 'metric-grid' });
  metrics.forEach((metric) => cards.appendChild(createIconStatCard(metric)));
  const table = createDataTable<LogRow & { dataFormatada: string }>({
    title: 'Logs do sistema',
    eyebrow: 'Histórico',
    rows: logs.map((log) => ({ ...log, dataFormatada: formattedLogDate(log) })),
    emptyMessage: loaded ? 'Nenhum log registrado ainda.' : 'Carregando logs...',
    onRowClick: (log) => openLogDrawer(log),
    columns: [
      { key: 'dataFormatada', label: 'Data/Hora' },
      { key: 'nivel', label: 'Nível' },
      { key: 'acao', label: 'Ação' },
      { key: 'mensagem', label: 'Mensagem' }
    ]
  });
  stack.append(cards, createLogEntityChart(logs), table);
  return stack;
}

function createLogEntityChart(logs: LogRow[]): HTMLElement {
  const counts = logs.reduce<Record<string, number>>((result, log) => {
    const entity = log.entidade || 'Sem entidade';
    result[entity] = (result[entity] ?? 0) + 1;
    return result;
  }, {});
  const entries = Object.entries(counts);
  const max = Math.max(...entries.map(([, count]) => count), 1);
  const panel = createElement('section', { className: 'log-entity-chart' });
  panel.appendChild(createPanelHeader('Logs por módulo', 'Distribuição por entidade nos registros carregados'));
  if (entries.length === 0) {
    panel.appendChild(createElement('p', { className: 'settings-hint', textContent: 'Nenhum registro para agrupar.' }));
    return panel;
  }
  entries.forEach(([entity, count]) => {
    const row = createElement('div', { className: 'log-entity-row' });
    const bar = createElement('span', { className: 'log-entity-bar' });
    bar.style.width = `${(count / max) * 100}%`;
    row.append(createElement('span', { textContent: entity }), bar, createElement('strong', { textContent: String(count) }));
    panel.appendChild(row);
  });
  return panel;
}

function openLogDrawer(log: LogRow): void {
  const content = createElement('div', { className: 'log-drawer-content' });
  const metadata = createElement('pre', { className: 'log-metadata' });
  metadata.textContent = JSON.stringify(log.metadados ?? {}, null, 2);
  content.append(
    createElement('p', { textContent: log.mensagem || log.acao }),
    createElement('span', { className: 'settings-hint', textContent: formattedLogDate(log) }),
    createElement('h3', { textContent: 'Metadados' }),
    metadata
  );
  const badge = createElement('span', { className: `log-level log-level-${log.nivel}`, textContent: log.nivel });
  const drawer = createDetailDrawer({
    title: log.acao,
    badge,
    tabs: [{ label: 'Detalhes', content }],
    onClose: () => drawer.remove()
  });
  document.body.appendChild(drawer);
}
