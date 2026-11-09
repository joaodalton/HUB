import { createIconStatCard } from '../../components/IconStatCard';
import { createUiState } from '../../components/UiState';
import { createElement } from '../../dom';
import { createPlatformLayout } from '../layouts/PlatformLayout';
import { getPlatformEmpresas, getPlatformOverview, type PlatformEmpresa } from '../services/platformService';
import { t } from '../../services/i18nService';

export function createPlatformOverviewPage(): HTMLElement {
  const content = createElement('div', { className: 'content-stack' });
  const metrics = createElement('section', { className: 'metric-grid platform-metrics' });
  metrics.setAttribute('aria-busy', 'true');
  metrics.append(createMetricPlaceholder(t('platform.overview.metricEmpresas')), createMetricPlaceholder(t('platform.overview.metricUsuarios')));
  const action = createElement('a', { className: 'data-panel platform-callout' });
  action.href = '/platform/companies';
  action.append(createElement('span', { className: 'eyebrow', textContent: t('platform.overview.calloutEyebrow') }), createElement('h2', { textContent: t('platform.overview.calloutTitle') }), createElement('p', { textContent: t('platform.overview.calloutDescription') }));
  action.addEventListener('click', (event) => { event.preventDefault(); window.history.pushState({}, '', action.href); window.dispatchEvent(new PopStateEvent('popstate')); });

  const shareSection = createElement('section', { className: 'data-panel' });
  shareSection.setAttribute('aria-busy', 'true');
  shareSection.append(
    createElement('h2', { textContent: t('platform.overview.shareTitle') }),
    createElement('p', { className: 'eyebrow', textContent: t('platform.overview.shareDescription') })
  );

  content.append(metrics, action, shareSection);

  void getPlatformOverview().then((overview) => {
    metrics.removeAttribute('aria-busy');
    metrics.replaceChildren(
      createIconStatCard({ icon: 'plants', chipColor: 'blue', value: String(overview.totalEmpresas), label: t('platform.overview.metricEmpresas') }),
      createIconStatCard({ icon: 'clients', chipColor: 'purple', value: String(overview.totalUsuarios), label: t('platform.overview.metricUsuarios') })
    );
  }).catch(() => {
    metrics.removeAttribute('aria-busy');
    metrics.replaceChildren(createUiState({ kind: 'error', title: t('platform.overview.loadError'), action: { label: t('platform.overview.retry'), onClick: () => window.dispatchEvent(new PopStateEvent('popstate')) } }));
  });

  void getPlatformEmpresas().then((empresas) => {
    shareSection.removeAttribute('aria-busy');
    shareSection.replaceChildren(
      createElement('h2', { textContent: t('platform.overview.shareTitle') }),
      createElement('p', { className: 'eyebrow', textContent: t('platform.overview.shareDescription') }),
      ...renderShareList(empresas)
    );
  }).catch(() => {
    shareSection.removeAttribute('aria-busy');
    shareSection.replaceChildren(
      createElement('h2', { textContent: t('platform.overview.shareTitle') }),
      createUiState({ kind: 'error', title: t('platform.overview.shareLoadError'), action: { label: t('platform.overview.retry'), onClick: () => window.dispatchEvent(new PopStateEvent('popstate')) } })
    );
  });

  return createPlatformLayout({ content, title: t('platform.overview.title'), description: t('platform.overview.description') });
}

function createMetricPlaceholder(label: string): HTMLElement {
  return createIconStatCard({ icon: 'dashboard', chipColor: 'blue', value: '—', label });
}

export function calculateShare(value: number, total: number): number {
  if (total <= 0) return 0;
  return Math.round((value / total) * 1000) / 10;
}

function renderShareList(empresas: PlatformEmpresa[]): HTMLElement[] {
  if (!empresas.length) {
    return [createUiState({ kind: 'empty', title: t('platform.overview.shareEmpty') })];
  }
  const totals = empresas.reduce(
    (acc, empresa) => ({
      ucs: acc.ucs + empresa.totalUcs,
      usinas: acc.usinas + empresa.totalUsinas,
      usuarios: acc.usuarios + empresa.totalUsuarios
    }),
    { ucs: 0, usinas: 0, usuarios: 0 }
  );

  const list = createElement('div', { className: 'platform-share-list' });
  list.append(...empresas.map((empresa) => createShareItem(empresa, totals)));
  return [list];
}

function createShareItem(empresa: PlatformEmpresa, totals: { ucs: number; usinas: number; usuarios: number }): HTMLElement {
  const item = createElement('div', { className: 'platform-share-item' });
  const bars = createElement('div', { className: 'platform-share-bars' });
  bars.append(
    createShareBarRow(t('platform.overview.shareUcs'), calculateShare(empresa.totalUcs, totals.ucs)),
    createShareBarRow(t('platform.overview.shareUsinas'), calculateShare(empresa.totalUsinas, totals.usinas)),
    createShareBarRow(t('platform.overview.shareUsuarios'), calculateShare(empresa.totalUsuarios, totals.usuarios))
  );
  item.append(createElement('h3', { textContent: empresa.nome }), bars);
  return item;
}

function createShareBarRow(label: string, percent: number): HTMLElement {
  const row = createElement('div', { className: 'platform-share-bar-row' });
  const track = createElement('div', { className: 'platform-share-bar-track' });
  track.setAttribute('role', 'progressbar');
  track.setAttribute('aria-valuemin', '0');
  track.setAttribute('aria-valuemax', '100');
  track.setAttribute('aria-valuenow', String(percent));
  track.setAttribute('aria-label', label);
  const fill = createElement('div', { className: 'platform-share-bar-fill' });
  fill.style.width = `${percent}%`;
  track.appendChild(fill);
  row.append(
    createElement('span', { textContent: label }),
    track,
    createElement('span', { textContent: `${percent}%` })
  );
  return row;
}
