import { createIconStatCard } from '../../components/IconStatCard';
import { createUiState } from '../../components/UiState';
import { createElement } from '../../dom';
import { createPlatformLayout } from '../layouts/PlatformLayout';
import { getPlatformOverview } from '../services/platformService';
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
  content.append(metrics, action);
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
  return createPlatformLayout({ content, title: t('platform.overview.title'), description: t('platform.overview.description') });
}

function createMetricPlaceholder(label: string): HTMLElement {
  return createIconStatCard({ icon: 'dashboard', chipColor: 'blue', value: '—', label });
}
