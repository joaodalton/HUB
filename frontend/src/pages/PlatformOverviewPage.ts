import { createIconStatCard } from '../components/IconStatCard';
import { createUiState } from '../components/UiState';
import { createElement } from '../dom';
import { createPlatformLayout } from '../layouts/PlatformLayout';
import { getPlatformOverview } from '../services/platformService';

export function createPlatformOverviewPage(): HTMLElement {
  const content = createElement('div', { className: 'content-stack' });
  const metrics = createElement('section', { className: 'metric-grid platform-metrics' });
  metrics.setAttribute('aria-busy', 'true');
  metrics.append(createMetricPlaceholder('Empresas'), createMetricPlaceholder('Usuários'));
  const action = createElement('a', { className: 'data-panel platform-callout' });
  action.href = '/platform/companies';
  action.append(createElement('span', { className: 'eyebrow', textContent: 'Contexto de empresa' }), createElement('h2', { textContent: 'Encontrar e entrar em uma empresa' }), createElement('p', { textContent: 'Selecione explicitamente o tenant antes de operar seus dados.' }));
  action.addEventListener('click', (event) => { event.preventDefault(); window.history.pushState({}, '', action.href); window.dispatchEvent(new PopStateEvent('popstate')); });
  content.append(metrics, action);
  void getPlatformOverview().then((overview) => {
    metrics.removeAttribute('aria-busy');
    metrics.replaceChildren(
      createIconStatCard({ icon: 'plants', chipColor: 'blue', value: String(overview.totalEmpresas), label: 'Empresas' }),
      createIconStatCard({ icon: 'clients', chipColor: 'purple', value: String(overview.totalUsuarios), label: 'Usuários' })
    );
  }).catch(() => {
    metrics.removeAttribute('aria-busy');
    metrics.replaceChildren(createUiState({ kind: 'error', title: 'Não foi possível carregar a visão geral.', action: { label: 'Tentar novamente', onClick: () => window.dispatchEvent(new PopStateEvent('popstate')) } }));
  });
  return createPlatformLayout({ content, title: 'Visão geral', description: 'Administração do HUB, separada do contexto operacional das empresas.' });
}

function createMetricPlaceholder(label: string): HTMLElement {
  return createIconStatCard({ icon: 'dashboard', chipColor: 'blue', value: '—', label });
}
