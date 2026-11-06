import { createIcon } from '../components/Icon';
import { createIconStatCard, type IconStatCardProps } from '../components/IconStatCard';
import { createListSkeleton } from '../components/UiState';
import { createElement } from '../dom';
import { useGlobalLoading } from '../hooks/useGlobalLoading';
import { createBaseLayout } from '../layouts/BaseLayout';
import { getDashboardResumo, type DashboardContagem, type DashboardPendencia, type DashboardResumo } from '../services/dashboardService';
import { prioridadeLabel, prioridadeTone, tipoLabel } from '../services/pendenciasService';
import { t } from '../services/i18nService';
import { formatDate, formatDateTime } from '../utils/date';

export function createDashboardPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const loading = useGlobalLoading();
  let resumo: DashboardResumo | null = null;
  let loadError = false;

  const layout = createBaseLayout({
    content,
    eyebrow: t('dashboard.eyebrow'),
    title: t('dashboard.title')
  });

  render();
  void loadResumo();
  return layout;

  async function loadResumo(): Promise<void> {
    loading.show();
    try {
      resumo = await getDashboardResumo();
      loadError = false;
    } catch {
      loadError = true;
    } finally {
      loading.hide();
      render();
    }
  }

  function render(): void {
    if (!resumo && !loadError) {
      content.replaceChildren(createListSkeleton(6));
      return;
    }

    if (loadError || !resumo) {
      const state = createElement('section', { className: 'dashboard-state empty-state' });
      state.append(
        createIcon('dashboard', 'empty-state-icon'),
        createElement('strong', { textContent: t('dashboard.loadError.title') }),
        createElement('span', { textContent: t('dashboard.loadError.description') })
      );
      const retry = createElement('button', { className: 'secondary-button', textContent: t('common.retry'), type: 'button' });
      retry.addEventListener('click', () => void loadResumo());
      state.appendChild(retry);
      content.replaceChildren(state);
      return;
    }

    const operationalMetrics: IconStatCardProps[] = [
      { label: t('dashboard.metric.pendingOpen'), value: String(resumo.pendencias.abertas), chipColor: 'amber', icon: 'pending', onClick: () => navigate('/pendencias') },
      { label: t('dashboard.metric.pendingOverdue'), value: String(resumo.pendencias.vencidas), chipColor: resumo.pendencias.vencidas > 0 ? 'red' : 'green', icon: 'pending', onClick: () => navigate('/pendencias') },
      { label: t('dashboard.metric.dueIn7Days'), value: String(resumo.pendencias.vencendoEm7Dias), chipColor: resumo.pendencias.vencendoEm7Dias > 0 ? 'amber' : 'green', icon: 'agenda', onClick: () => navigate('/agenda') },
      { label: t('dashboard.metric.resolvedThisMonth'), value: String(resumo.pendencias.resolvidasNoMes), chipColor: 'green', icon: 'check', onClick: () => navigate('/pendencias') }
    ];

    const entityMetrics: Array<IconStatCardProps | null> = [
      metricForEntity(t('dashboard.entity.clients'), resumo.clientes, 'clients', '/clientes'),
      metricForEntity(t('dashboard.entity.ucs'), resumo.ucs, 'ucs', '/ucs'),
      metricForEntity(t('dashboard.entity.plants'), resumo.usinas, 'plants', '/usinas'),
      metricForEntity(t('dashboard.entity.documents'), resumo.documentos, 'documents', '/documentos')
    ];
    const availableEntityMetrics = entityMetrics.filter((metric): metric is IconStatCardProps => metric !== null);

    const summary = createElement('section', { className: 'dashboard-summary' });
    summary.append(
      createElement('span', { className: 'dashboard-updated', textContent: `${t('dashboard.updatedAt')} ${formatDateTime(resumo.geradoEm)}` }),
      createElement('h2', { textContent: t('dashboard.operation') }),
      createStatGrid(operationalMetrics)
    );
    if (availableEntityMetrics.length) summary.append(createElement('h2', { textContent: t('dashboard.registrations') }), createStatGrid(availableEntityMetrics));

    content.replaceChildren(summary, createQueue(resumo.pendencias.fila));
  }
}

function metricForEntity(label: string, data: DashboardContagem, icon: IconStatCardProps['icon'], path: string): IconStatCardProps | null {
  if (!data.disponivel || data.total === null) return null;
  return { label, value: String(data.total ?? 0), chipColor: 'blue', icon, onClick: () => navigate(path) };
}

function createStatGrid(metrics: IconStatCardProps[]): HTMLElement {
  const grid = createElement('section', { className: 'metric-grid' });
  metrics.forEach((metric) => grid.appendChild(createIconStatCard(metric)));
  return grid;
}

function createQueue(items: DashboardPendencia[]): HTMLElement {
  const panel = createElement('section', { className: 'dashboard-queue' });
  const header = createElement('div', { className: 'dashboard-queue-header' });
  header.append(
    createElement('div', { className: 'dashboard-queue-title' }),
    createElement('a', { className: 'dashboard-queue-link', textContent: t('dashboard.viewAll') })
  );
  const title = header.querySelector('.dashboard-queue-title') as HTMLElement;
  title.append(createElement('span', { className: 'eyebrow', textContent: t('dashboard.priority') }), createElement('h2', { textContent: t('dashboard.queueTitle') }));
  const link = header.querySelector('.dashboard-queue-link') as HTMLAnchorElement;
  link.href = '/pendencias';
  link.addEventListener('click', (event) => { event.preventDefault(); navigate('/pendencias'); });
  panel.appendChild(header);

  if (items.length === 0) {
    panel.appendChild(createElement('p', {
      className: 'empty-state small',
      textContent: t('dashboard.queueEmpty')
    }));
    return panel;
  }

  const list = createElement('div', { className: 'dashboard-queue-list' });
  items.forEach((item) => {
    const row = createElement('a', { className: 'dashboard-queue-item' });
    row.href = `/pendencias?selecionada=${item.id}`;
    row.addEventListener('click', (event) => { event.preventDefault(); navigate(row.href); });
    const info = createElement('div', { className: 'dashboard-queue-info' });
    info.append(
      createElement('strong', { textContent: item.titulo }),
      createElement('span', { textContent: itemContext(item) })
    );
    const meta = createElement('div', { className: 'dashboard-queue-meta' });
    meta.append(
      createElement('span', { className: 'status-badge', textContent: tipoLabel(item.tipo) }),
      createElement('span', { className: prioridadeTone(item.prioridade) === 'neutral' ? 'status-badge' : `status-badge tone-${prioridadeTone(item.prioridade)}`, textContent: prioridadeLabel(item.prioridade) }),
      createElement('time', { textContent: item.prazo ? `${t('dashboard.deadline')}: ${formatDate(item.prazo)}` : t('dashboard.noDeadline') })
    );
    row.append(info, meta);
    list.appendChild(row);
  });
  panel.appendChild(list);
  return panel;
}

function itemContext(item: DashboardPendencia): string {
  const values = [
    item.clienteNome ? `${t('dashboard.context.client')}: ${item.clienteNome}` : null,
    item.ucCodigo ? `${t('dashboard.context.uc')}: ${item.ucCodigo}` : null,
    item.usinaNome ? `${t('dashboard.context.plant')}: ${item.usinaNome}` : null
  ].filter((value): value is string => value !== null);
  return values.join(' · ') || t('dashboard.context.none');
}

function navigate(path: string): void {
  window.history.pushState({}, '', path);
  window.dispatchEvent(new PopStateEvent('popstate'));
}
