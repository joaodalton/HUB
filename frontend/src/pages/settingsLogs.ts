import { createElement } from '../dom';
import { createDataTable } from '../components/DataTable';
import { createDetailDrawer } from '../components/DetailDrawer';
import { createIconStatCard, type IconStatCardProps } from '../components/IconStatCard';
import { formattedLogDate, type LogRow } from '../services/logsService';
import { createPanelHeader } from './settingsShared';
import { t } from '../services/i18nService';

// ---------- Home ----------

export function createHomePanel(
  logs: LogRow[],
  logsLoaded: boolean,
  onSeeAllLogs: () => void
): HTMLElement {
  const logsCard = createElement('section', { className: 'settings-panel' });
  const seeAllButton = createElement('button', { className: 'secondary-link', textContent: t('settings.logs.seeAll'), type: 'button' });
  seeAllButton.addEventListener('click', onSeeAllLogs);
  logsCard.appendChild(createPanelHeader(t('settings.logs.recentHeading'), t('settings.logs.recentDescription'), seeAllButton));

  if (!logsLoaded) {
    logsCard.appendChild(createElement('p', { className: 'settings-hint', textContent: t('settings.logs.loading') }));
  } else if (logs.length === 0) {
    logsCard.appendChild(createElement('p', { className: 'settings-hint', textContent: t('settings.logs.none') }));
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
    { label: t('settings.logs.infoLabel'), value: String(logs.filter((log) => log.nivel === 'info').length), chipColor: 'blue', icon: 'dashboard' },
    { label: t('settings.logs.alertsLabel'), value: String(logs.filter((log) => log.nivel === 'warning').length), chipColor: 'amber', icon: 'pending' },
    { label: t('settings.logs.errorsLabel'), value: String(logs.filter((log) => log.nivel === 'error').length), chipColor: 'red', icon: 'x' }
  ];
  const cards = createElement('section', { className: 'metric-grid' });
  metrics.forEach((metric) => cards.appendChild(createIconStatCard(metric)));
  const table = createDataTable<LogRow & { dataFormatada: string }>({
    title: t('settings.logs.systemLogsTitle'),
    eyebrow: t('settings.logs.historyEyebrow'),
    rows: logs.map((log) => ({ ...log, dataFormatada: formattedLogDate(log) })),
    emptyMessage: loaded ? t('settings.logs.none') : t('settings.logs.loading'),
    onRowClick: (log) => openLogDrawer(log),
    columns: [
      { key: 'dataFormatada', label: t('settings.logs.dateColumn') },
      { key: 'nivel', label: t('settings.logs.levelColumn') },
      { key: 'mensagem', label: t('settings.logs.messageColumn') }
    ]
  });
  stack.append(cards, createLogEntityChart(logs), table);
  return stack;
}

function createLogEntityChart(logs: LogRow[]): HTMLElement {
  const counts = logs.reduce<Record<string, number>>((result, log) => {
    const entity = log.entidade || t('settings.logs.noEntity');
    result[entity] = (result[entity] ?? 0) + 1;
    return result;
  }, {});
  const entries = Object.entries(counts);
  const max = Math.max(...entries.map(([, count]) => count), 1);
  const panel = createElement('section', { className: 'log-entity-chart' });
  panel.appendChild(createPanelHeader(t('settings.logs.byModuleHeading'), t('settings.logs.byModuleDescription')));
  if (entries.length === 0) {
    panel.appendChild(createElement('p', { className: 'settings-hint', textContent: t('settings.logs.noneToGroup') }));
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

// Rotulos amigaveis so pra acoes mais comuns -- nao e um sistema de
// traducao pra todo slug do backend, so cobre os mais frequentes. O resto
// cai no fallback humanizeAction().
function actionLabels(): Record<string, string> {
  return {
    login: t('settings.logs.actionLogin'),
    login_failed: t('settings.logs.actionLoginFailed'),
    email_sent: t('settings.logs.actionEmailSent'),
    email_failed: t('settings.logs.actionEmailFailed'),
    email_not_configured: t('settings.logs.actionEmailNotConfigured'),
    create: t('settings.logs.actionCreate'),
    update: t('settings.logs.actionUpdate'),
    delete: t('settings.logs.actionDelete'),
    download: t('settings.logs.actionDownload')
  };
}

function humanizeAction(acao: string): string {
  const labels = actionLabels();
  if (labels[acao]) return labels[acao];
  const text = acao.replace(/_/g, ' ');
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function openLogDrawer(log: LogRow): void {
  const content = createElement('div', { className: 'log-drawer-content' });
  const isError = log.nivel === 'error';
  const message = createElement('p', {
    className: isError ? 'log-drawer-message log-drawer-message-error' : 'log-drawer-message',
    textContent: log.mensagem || humanizeAction(log.acao)
  });
  content.append(
    message,
    createElement('span', { className: 'settings-hint', textContent: formattedLogDate(log) })
  );
  const badge = createElement('span', { className: `log-level log-level-${log.nivel}`, textContent: log.nivel });
  const drawer = createDetailDrawer({
    title: humanizeAction(log.acao),
    badge,
    tabs: [{ label: t('settings.logs.detailsTab'), content }],
    onClose: () => drawer.remove()
  });
  document.body.appendChild(drawer);
}
