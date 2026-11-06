import { createElement } from '../../dom';
import { createStatusBadge } from '../../components/StatusBadge';
import { createUiState } from '../../components/UiState';
import { createPlatformLayout } from '../layouts/PlatformLayout';
import { getNeonStorage, type NeonEnvironmentStorage, type NeonStorageSummary } from '../services/platformService';
import { t } from '../../services/i18nService';

export function createPlatformStoragePage(): HTMLElement {
  const content = createElement('div', { className: 'content-stack' });
  content.setAttribute('aria-busy', 'true');
  content.appendChild(createElement('p', { className: 'eyebrow', textContent: t('platform.storage.loading') }));

  void getNeonStorage()
    .then((summary) => {
      content.removeAttribute('aria-busy');
      content.replaceChildren(...renderSummary(summary));
    })
    .catch((error) => {
      content.removeAttribute('aria-busy');
      content.replaceChildren(createUiState({
        kind: 'error',
        title: t('platform.storage.loadError'),
        description: error instanceof Error ? error.message : undefined,
        action: { label: t('platform.storage.retry'), onClick: () => window.dispatchEvent(new PopStateEvent('popstate')) }
      }));
    });

  return createPlatformLayout({
    content,
    title: t('platform.storage.title'),
    description: t('platform.storage.description')
  });
}

function renderSummary(summary: NeonStorageSummary): HTMLElement[] {
  if (!summary.ambientes.length) {
    return [createUiState({
      kind: 'empty',
      title: t('platform.storage.emptyTitle'),
      description: t('platform.storage.emptyDescription')
    })];
  }
  return summary.ambientes.map((ambiente) => createEnvironmentCard(ambiente, ambiente.ambiente === summary.ambienteAtual));
}

function createEnvironmentCard(ambiente: NeonEnvironmentStorage, isAtivo: boolean): HTMLElement {
  const card = createElement('section', { className: 'data-panel' });

  const header = createElement('div', { className: 'detail-title-row' });
  header.append(
    createElement('h2', { textContent: ambiente.ambiente === 'producao' ? t('platform.storage.envProducao') : t('platform.storage.envDesenvolvimento') }),
    isAtivo ? createStatusBadge(t('platform.storage.ambienteAtivo'), 'success') : createStatusBadge(t('platform.storage.inativo'), 'warning')
  );

  const projectInfo = createElement('p', { className: 'eyebrow', textContent: t('platform.storage.projetoNeonTemplate').replace('{id}', ambiente.projectId) });

  const total = createElement('div', { className: 'plant-summary-row' });
  const totalLabel = ambiente.limiteBytes
    ? t('platform.storage.totalUsadoDeTemplate').replace('{used}', formatBytes(ambiente.totalBytes)).replace('{limit}', formatBytes(ambiente.limiteBytes))
    : formatBytes(ambiente.totalBytes);
  total.append(
    createElement('span', { textContent: t('platform.storage.totalUsado') }),
    createElement('strong', { textContent: totalLabel })
  );

  const version = createElement('div', { className: 'plant-summary-row' });
  version.append(
    createElement('span', { textContent: t('platform.storage.versaoPostgres') }),
    createElement('strong', { textContent: ambiente.pgVersion ? String(ambiente.pgVersion) : '—' })
  );

  const compute = createElement('div', { className: 'plant-summary-row' });
  compute.append(
    createElement('span', { textContent: t('platform.storage.statusCompute') }),
    createComputeStatusBadge(ambiente.computeStatus)
  );

  const branchRows = createElement('div', { className: 'plant-summary-rows' });
  branchRows.append(...ambiente.branches.map((branch) => {
    const row = createElement('div', { className: 'plant-summary-row' });
    row.append(
      createElement('span', { textContent: branch.nome }),
      createElement('strong', { textContent: formatBytes(branch.tamanhoBytes) })
    );
    return row;
  }));

  card.append(header, projectInfo, total, version, compute, branchRows);
  return card;
}

function createComputeStatusBadge(status: string | null): HTMLElement {
  if (!status) return createStatusBadge(t('platform.storage.computeDesconhecido'), 'neutral');
  if (status === 'active') return createStatusBadge(t('platform.storage.computeAtivo'), 'success');
  if (status === 'idle') return createStatusBadge(t('platform.storage.computeHibernado'), 'info');
  return createStatusBadge(status, 'warning');
}

function formatBytes(bytes: number): string {
  if (bytes <= 0) return '0 MB';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / Math.pow(1024, exponent);
  return `${value.toFixed(exponent === 0 ? 0 : 2)} ${units[exponent]}`;
}
