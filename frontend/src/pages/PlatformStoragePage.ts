import { createElement } from '../dom';
import { createStatusBadge } from '../components/StatusBadge';
import { createUiState } from '../components/UiState';
import { createPlatformLayout } from '../layouts/PlatformLayout';
import { getNeonStorage, type NeonEnvironmentStorage, type NeonStorageSummary } from '../services/platformService';

export function createPlatformStoragePage(): HTMLElement {
  const content = createElement('div', { className: 'content-stack' });
  content.setAttribute('aria-busy', 'true');
  content.appendChild(createElement('p', { className: 'eyebrow', textContent: 'Carregando armazenamento do Neon...' }));

  void getNeonStorage()
    .then((summary) => {
      content.removeAttribute('aria-busy');
      content.replaceChildren(...renderSummary(summary));
    })
    .catch((error) => {
      content.removeAttribute('aria-busy');
      content.replaceChildren(createUiState({
        kind: 'error',
        title: 'Não foi possível carregar o armazenamento do Neon.',
        description: error instanceof Error ? error.message : undefined,
        action: { label: 'Tentar novamente', onClick: () => window.dispatchEvent(new PopStateEvent('popstate')) }
      }));
    });

  return createPlatformLayout({
    content,
    title: 'Armazenamento',
    description: 'Uso de armazenamento do banco Postgres (Neon) por ambiente. Somente leitura — trocar o ambiente ativo exige reconfigurar DATABASE_URL e reiniciar o backend.'
  });
}

function renderSummary(summary: NeonStorageSummary): HTMLElement[] {
  if (!summary.ambientes.length) {
    return [createUiState({
      kind: 'empty',
      title: 'Nenhum projeto Neon configurado.',
      description: 'Defina NEON_API_KEY e NEON_PROJECT_ID_DEV/NEON_PROJECT_ID_PROD no ambiente do backend.'
    })];
  }
  return summary.ambientes.map((ambiente) => createEnvironmentCard(ambiente, ambiente.ambiente === summary.ambienteAtual));
}

function createEnvironmentCard(ambiente: NeonEnvironmentStorage, isAtivo: boolean): HTMLElement {
  const card = createElement('section', { className: 'data-panel' });

  const header = createElement('div', { className: 'detail-title-row' });
  header.append(
    createElement('h2', { textContent: ambiente.ambiente === 'producao' ? 'Produção' : 'Desenvolvimento' }),
    isAtivo ? createStatusBadge('Ambiente ativo', 'success') : createStatusBadge('Inativo', 'warning')
  );

  const projectInfo = createElement('p', { className: 'eyebrow', textContent: `Projeto Neon: ${ambiente.projectId}` });

  const total = createElement('div', { className: 'plant-summary-row' });
  const totalLabel = ambiente.limiteBytes
    ? `${formatBytes(ambiente.totalBytes)} de ${formatBytes(ambiente.limiteBytes)}`
    : formatBytes(ambiente.totalBytes);
  total.append(
    createElement('span', { textContent: 'Total usado' }),
    createElement('strong', { textContent: totalLabel })
  );

  const version = createElement('div', { className: 'plant-summary-row' });
  version.append(
    createElement('span', { textContent: 'Versão do Postgres' }),
    createElement('strong', { textContent: ambiente.pgVersion ? String(ambiente.pgVersion) : '—' })
  );

  const compute = createElement('div', { className: 'plant-summary-row' });
  compute.append(
    createElement('span', { textContent: 'Status do compute' }),
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
  if (!status) return createStatusBadge('Desconhecido', 'neutral');
  if (status === 'active') return createStatusBadge('Ativo', 'success');
  if (status === 'idle') return createStatusBadge('Hibernado (inatividade)', 'info');
  return createStatusBadge(status, 'warning');
}

function formatBytes(bytes: number): string {
  if (bytes <= 0) return '0 MB';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / Math.pow(1024, exponent);
  return `${value.toFixed(exponent === 0 ? 0 : 2)} ${units[exponent]}`;
}
