import { createIcon } from '../components/Icon';
import { createIconStatCard, type IconStatCardProps } from '../components/IconStatCard';
import { createElement } from '../dom';
import { useGlobalLoading } from '../hooks/useGlobalLoading';
import { createBaseLayout } from '../layouts/BaseLayout';
import { getDashboardResumo, type DashboardContagem, type DashboardPendencia, type DashboardResumo } from '../services/dashboardService';
import { prioridadeLabel, prioridadeTone, tipoLabel } from '../services/pendenciasService';

export function createDashboardPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const loading = useGlobalLoading();
  let resumo: DashboardResumo | null = null;
  let loadError = false;

  const layout = createBaseLayout({
    content,
    eyebrow: 'Dashboard',
    title: 'Visão operacional da sua empresa'
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
      content.replaceChildren(createElement('section', {
        className: 'dashboard-state loading-state',
        textContent: 'Carregando resumo operacional...'
      }));
      return;
    }

    if (loadError || !resumo) {
      const state = createElement('section', { className: 'dashboard-state empty-state' });
      state.append(
        createIcon('dashboard', 'empty-state-icon'),
        createElement('strong', { textContent: 'Não foi possível carregar o dashboard.' }),
        createElement('span', { textContent: 'Verifique sua conexão e tente novamente.' })
      );
      const retry = createElement('button', { className: 'secondary-button', textContent: 'Tentar novamente', type: 'button' });
      retry.addEventListener('click', () => void loadResumo());
      state.appendChild(retry);
      content.replaceChildren(state);
      return;
    }

    const operationalMetrics: IconStatCardProps[] = [
      { label: 'Pendências abertas', value: String(resumo.pendencias.abertas), chipColor: 'amber', icon: 'pending', onClick: () => navigate('/pendencias') },
      { label: 'Pendências vencidas', value: String(resumo.pendencias.vencidas), chipColor: resumo.pendencias.vencidas > 0 ? 'red' : 'green', icon: 'pending', onClick: () => navigate('/pendencias') },
      { label: 'Vencem em 7 dias', value: String(resumo.pendencias.vencendoEm7Dias), chipColor: resumo.pendencias.vencendoEm7Dias > 0 ? 'amber' : 'green', icon: 'agenda', onClick: () => navigate('/agenda') },
      { label: 'Concluídas no mês', value: String(resumo.pendencias.resolvidasNoMes), chipColor: 'green', icon: 'check', onClick: () => navigate('/pendencias') }
    ];

    const entityMetrics = [
      metricForEntity('Clientes', resumo.clientes, 'clients', '/clientes'),
      metricForEntity('UCs', resumo.ucs, 'ucs', '/ucs'),
      metricForEntity('Usinas', resumo.usinas, 'plants', '/usinas'),
      metricForEntity('Documentos', resumo.documentos, 'documents', '/documentos')
    ];

    const summary = createElement('section', { className: 'dashboard-summary' });
    summary.append(
      createElement('span', { className: 'dashboard-updated', textContent: `Atualizado ${formatDateTime(resumo.geradoEm)}` }),
      createElement('h2', { textContent: 'Operação' }),
      createStatGrid(operationalMetrics),
      createElement('h2', { textContent: 'Cadastros' }),
      createStatGrid(entityMetrics),
      createStatusCharts(resumo)
    );

    content.replaceChildren(summary, createQueue(resumo.pendencias.fila));
  }
}

function metricForEntity(label: string, data: DashboardContagem, icon: IconStatCardProps['icon'], path: string): IconStatCardProps {
  if (!data.disponivel) {
    return { label: `${label} sem permissão`, value: '—', chipColor: 'purple', icon };
  }
  return { label, value: String(data.total ?? 0), chipColor: 'blue', icon, onClick: () => navigate(path) };
}

function createStatGrid(metrics: IconStatCardProps[]): HTMLElement {
  const grid = createElement('section', { className: 'metric-grid' });
  metrics.forEach((metric) => grid.appendChild(createIconStatCard(metric)));
  return grid;
}

function createStatusCharts(resumo: DashboardResumo): HTMLElement {
  const grid = createElement('section', { className: 'dashboard-status-grid' });
  [
    ['Status dos clientes', resumo.clientes],
    ['Status das usinas', resumo.usinas]
  ].forEach(([title, data]) => {
    const chart = createStatusChart(title as string, data as DashboardContagem);
    if (chart) grid.appendChild(chart);
  });
  return grid;
}

function createStatusChart(title: string, data: DashboardContagem): HTMLElement | null {
  const entries = Object.entries(data.porStatus ?? {}).filter(([, count]) => count > 0);
  if (!data.disponivel || entries.length === 0) return null;

  const colors = ['var(--accent-secondary)', 'var(--success-vivid)', 'var(--warning-vivid)', 'var(--danger-vivid)', 'var(--chip-purple-fg)'];
  const total = entries.reduce((sum, [, count]) => sum + count, 0);
  let offset = 0;
  const stops = entries.map(([, count], index) => {
    const end = offset + (count / total) * 100;
    const stop = `${colors[index % colors.length]} ${offset}% ${end}%`;
    offset = end;
    return stop;
  });
  const panel = createElement('section', { className: 'dashboard-status-chart' });
  const donut = createElement('span', { className: 'dashboard-donut' });
  donut.style.background = `conic-gradient(${stops.join(', ')})`;
  donut.appendChild(createElement('span', { textContent: String(total) }));
  const legend = createElement('div', { className: 'dashboard-status-legend' });
  entries.forEach(([status, count], index) => {
    const item = createElement('span', { textContent: `${status}: ${count}` });
    item.style.setProperty('--status-color', colors[index % colors.length]);
    legend.appendChild(item);
  });
  panel.append(createElement('h2', { textContent: title }), donut, legend);
  return panel;
}

function createQueue(items: DashboardPendencia[]): HTMLElement {
  const panel = createElement('section', { className: 'dashboard-queue' });
  const header = createElement('div', { className: 'dashboard-queue-header' });
  header.append(
    createElement('div', { className: 'dashboard-queue-title' }),
    createElement('a', { className: 'dashboard-queue-link', textContent: 'Ver todas' })
  );
  const title = header.querySelector('.dashboard-queue-title') as HTMLElement;
  title.append(createElement('span', { className: 'eyebrow', textContent: 'Prioridade' }), createElement('h2', { textContent: 'Fila operacional' }));
  const link = header.querySelector('.dashboard-queue-link') as HTMLAnchorElement;
  link.href = '/pendencias';
  link.addEventListener('click', (event) => { event.preventDefault(); navigate('/pendencias'); });
  panel.appendChild(header);

  if (items.length === 0) {
    panel.appendChild(createElement('p', {
      className: 'empty-state small',
      textContent: 'Nenhuma pendência aberta no momento.'
    }));
    return panel;
  }

  const list = createElement('div', { className: 'dashboard-queue-list' });
  items.forEach((item) => {
    const row = createElement('a', { className: 'dashboard-queue-item' });
    row.href = '/pendencias';
    row.addEventListener('click', (event) => { event.preventDefault(); navigate('/pendencias'); });
    const info = createElement('div', { className: 'dashboard-queue-info' });
    info.append(
      createElement('strong', { textContent: item.titulo }),
      createElement('span', { textContent: itemContext(item) })
    );
    const meta = createElement('div', { className: 'dashboard-queue-meta' });
    meta.append(
      createElement('span', { className: 'status-badge', textContent: tipoLabel(item.tipo) }),
      createElement('span', { className: prioridadeTone(item.prioridade) === 'neutral' ? 'status-badge' : `status-badge tone-${prioridadeTone(item.prioridade)}`, textContent: prioridadeLabel(item.prioridade) }),
      createElement('time', { textContent: item.prazo ? `Prazo: ${formatDate(item.prazo)}` : 'Sem prazo' })
    );
    row.append(info, meta);
    list.appendChild(row);
  });
  panel.appendChild(list);
  return panel;
}

function itemContext(item: DashboardPendencia): string {
  const values = [
    item.clienteNome ? `Cliente: ${item.clienteNome}` : null,
    item.ucCodigo ? `UC: ${item.ucCodigo}` : null,
    item.usinaNome ? `Usina: ${item.usinaNome}` : null
  ].filter((value): value is string => value !== null);
  return values.join(' · ') || 'Sem vínculo cadastrado';
}

function formatDate(value: string): string {
  return new Date(value).toLocaleDateString('pt-BR');
}

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
}

function navigate(path: string): void {
  window.history.pushState({}, '', path);
  window.dispatchEvent(new PopStateEvent('popstate'));
}
