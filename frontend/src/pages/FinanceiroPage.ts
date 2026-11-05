// frontend/src/pages/FinanceiroPage.ts
import { createElement } from '../dom';
import { createDataTable } from '../components/DataTable';
import { createIconStatCard } from '../components/IconStatCard';
import { createStatusBadge, type StatusTone } from '../components/StatusBadge';
import { formatCurrency } from '../components/FaturasUi';
import { useGlobalLoading } from '../hooks/useGlobalLoading';
import { useToast } from '../hooks/useToast';
import { createBaseLayout } from '../layouts/BaseLayout';
import { getFinanceiroDashboard, type FinanceiroDashboard } from '../services/financeiroService';
import {
  getPendencias,
  prioridadeLabel,
  prioridadeTone,
  statusLabel,
  vinculacaoLabel,
  type PendenciaRow,
  type PendenciaStatus
} from '../services/pendenciasService';
import { t } from '../services/i18nService';

type FinanceiroTab = 'clientes' | 'usinas';

export function createFinanceiroPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const toast = useToast();
  const loading = useGlobalLoading();

  let activeTab: FinanceiroTab = 'clientes';
  let dashboard: FinanceiroDashboard = { porCliente: [], porUsina: [] };
  let pendenciasCobrarConcessionaria: PendenciaRow[] = [];
  let pendenciasFaturaGeracao: PendenciaRow[] = [];
  let pendenciasRepasseUsineiro: PendenciaRow[] = [];
  let loadError = false;
  let isLoading = true;

  const layout = createBaseLayout({
    content,
    eyebrow: t('financeiro.page.eyebrow'),
    title: t('financeiro.page.title'),
    description: t('financeiro.page.description')
  });

  renderContent();
  void loadAll();

  return layout;

  async function loadAll(): Promise<void> {
    isLoading = true;
    loading.show();
    try {
      const [dashboardData, cobrarConcessionaria, faturaGeracao, repasseUsineiro] = await Promise.all([
        getFinanceiroDashboard(),
        getPendencias({ origem: 'pagar_concessionaria' }),
        getPendencias({ origem: 'fatura_geracao_usina' }),
        getPendencias({ origem: 'repasse_usineiro' })
      ]);
      dashboard = dashboardData;
      pendenciasCobrarConcessionaria = cobrarConcessionaria;
      pendenciasFaturaGeracao = faturaGeracao;
      pendenciasRepasseUsineiro = repasseUsineiro;
      loadError = false;
    } catch (cause) {
      loadError = true;
      toast.error(cause instanceof Error ? cause.message : t('financeiro.page.loadError'));
    } finally {
      isLoading = false;
      loading.hide();
      renderContent();
    }
  }

  function changeTab(tab: FinanceiroTab): void {
    activeTab = tab;
    renderContent();
  }

  function renderContent(): void {
    const tabs = createElement('div', { className: 'page-actions' });
    tabs.append(
      createTabButton('clientes', t('financeiro.page.tabClientes')),
      createTabButton('usinas', t('financeiro.page.tabUsinas'))
    );
    const panel = activeTab === 'clientes' ? renderClientesTab() : renderUsinasTab();
    content.replaceChildren(tabs, panel);
  }

  function createTabButton(tab: FinanceiroTab, label: string): HTMLElement {
    const button = createElement('button', {
      className: activeTab === tab ? 'secondary-button active' : 'secondary-button',
      type: 'button',
      textContent: label
    });
    button.addEventListener('click', () => changeTab(tab));
    return button;
  }

  function renderClientesTab(): HTMLElement {
    const fragment = createElement('div', { className: 'content-stack' });

    const totalRecebido = dashboard.porCliente.reduce((sum, item) => sum + Number(item.recebido || 0), 0);
    const totalPendente = dashboard.porCliente.reduce((sum, item) => sum + Number(item.pendente || 0), 0);

    const grid = createElement('section', { className: 'metric-grid' });
    grid.append(
      createIconStatCard({ icon: 'cobrancas', chipColor: 'green', value: formatCurrency(totalRecebido), label: t('financeiro.page.totalRecebido') }),
      createIconStatCard({ icon: 'pending', chipColor: 'amber', value: formatCurrency(totalPendente), label: t('financeiro.page.totalPendente') })
    );

    const cobrarLink = createElement('a', { className: 'button-with-icon', textContent: t('financeiro.page.readyToCharge') });
    cobrarLink.href = '/faturas?cobranca=sem_cobranca';
    cobrarLink.addEventListener('click', (event) => {
      event.preventDefault();
      navigateTo('/faturas?cobranca=sem_cobranca');
    });
    const cobrarAction = createElement('div', { className: 'page-actions' });
    cobrarAction.appendChild(cobrarLink);

    fragment.append(grid, cobrarAction, createPendenciasTable(
      t('financeiro.page.pendenciasConcessionaria'),
      pendenciasCobrarConcessionaria
    ));
    return fragment;
  }

  function renderUsinasTab(): HTMLElement {
    const fragment = createElement('div', { className: 'content-stack' });

    const grid = createElement('section', { className: 'metric-grid' });
    dashboard.porUsina.forEach((usina) => {
      const semClientes = 'semClientesConectados' in usina && usina.semClientesConectados === true;
      const aguardandoPagamentos = 'aguardandoPagamentos' in usina && usina.aguardandoPagamentos === true;
      const trend = semClientes
        ? t('financeiro.page.semClientesConectados')
        : usina.contratoPendente
          ? t('financeiro.page.contratoPendente')
          : aguardandoPagamentos
            ? t('financeiro.page.aguardandoPagamentos')
            : `${t('financeiro.page.repasse')}: ${formatCurrency(usina.repasseCalculado)}`;
      grid.appendChild(createIconStatCard({
        icon: 'plants',
        chipColor: usina.contratoPendente || semClientes || aguardandoPagamentos ? 'amber' : 'green',
        value: formatCurrency(usina.recebido),
        label: usina.usinaNome,
        trend
      }));
    });

    fragment.append(
      grid,
      createPendenciasTable(t('financeiro.page.pendenciasFaturaGeracao'), pendenciasFaturaGeracao),
      createPendenciasTable(t('financeiro.page.pendenciasRepasseUsineiro'), pendenciasRepasseUsineiro)
    );
    return fragment;
  }

  function createPendenciasTable(title: string, rows: PendenciaRow[]): HTMLElement {
    return createDataTable<PendenciaRow>({
      title,
      eyebrow: isLoading ? t('financeiro.page.loadingShort') : `${rows.length} ${rows.length === 1 ? t('financeiro.page.recordSingular') : t('financeiro.page.recordPlural')}`,
      rows: loadError || isLoading ? [] : rows,
      emptyMessage: loadError ? t('financeiro.page.pendenciasLoadError') : t('financeiro.page.pendenciasEmpty'),
      state: isLoading ? 'loading' : loadError ? 'error' : 'ready',
      stateTitle: loadError ? t('financeiro.page.pendenciasLoadError') : t('financeiro.page.pendenciasEmpty'),
      errorAction: { label: t('common.retry'), onClick: () => void loadAll() },
      onRowClick: (item) => navigateTo(`/pendencias?selecionada=${item.id}`),
      columns: [
        { key: 'titulo', label: t('financeiro.page.colPendencia') },
        { key: 'vinculacao', label: t('financeiro.page.colVinculacao'), render: (item) => vinculacaoLabel(item) },
        { key: 'prioridade', label: t('financeiro.page.colPrioridade'), render: (item) => createStatusBadge(prioridadeLabel(item.prioridade), prioridadeTone(item.prioridade) as StatusTone) },
        { key: 'status', label: t('financeiro.page.colStatus'), render: (item) => createStatusBadge(statusLabel(item.status), statusTone(item.status)) }
      ]
    });
  }
}

function statusTone(status: PendenciaStatus): StatusTone {
  return status === 'aberta' ? 'warning' : status === 'resolvida' ? 'success' : 'neutral';
}

function navigateTo(path: string): void {
  window.history.pushState({}, '', path);
  window.dispatchEvent(new PopStateEvent('popstate'));
}
