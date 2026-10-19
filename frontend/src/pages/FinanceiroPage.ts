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
    eyebrow: 'Financeiro',
    title: 'Financeiro',
    description: 'Visão consolidada de recebimentos de clientes e repasses de usinas.'
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
      toast.error(cause instanceof Error ? cause.message : 'Não foi possível carregar o financeiro.');
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
      createTabButton('clientes', 'Clientes/UCs'),
      createTabButton('usinas', 'Usinas')
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
      createIconStatCard({ icon: 'cobrancas', chipColor: 'green', value: formatCurrency(totalRecebido), label: 'Total recebido' }),
      createIconStatCard({ icon: 'pending', chipColor: 'amber', value: formatCurrency(totalPendente), label: 'Total pendente' })
    );

    const cobrarLink = createElement('a', { className: 'button-with-icon', textContent: 'Faturas prontas para cobrar' });
    cobrarLink.href = '/faturas?cobranca=sem_cobranca';
    cobrarLink.addEventListener('click', (event) => {
      event.preventDefault();
      navigateTo('/faturas?cobranca=sem_cobranca');
    });
    const cobrarAction = createElement('div', { className: 'page-actions' });
    cobrarAction.appendChild(cobrarLink);

    fragment.append(grid, cobrarAction, createPendenciasTable(
      'Pagamentos à concessionária pendentes',
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
        ? 'Sem clientes conectados'
        : usina.contratoPendente
          ? 'Contrato de repasse pendente de configurar'
          : aguardandoPagamentos
            ? 'Aguardando confirmação de pagamento de todos os clientes'
            : `Repasse: ${formatCurrency(usina.repasseCalculado)}`;
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
      createPendenciasTable('Faturas de geração pendentes', pendenciasFaturaGeracao),
      createPendenciasTable('Repasses ao usineiro pendentes', pendenciasRepasseUsineiro)
    );
    return fragment;
  }

  function createPendenciasTable(title: string, rows: PendenciaRow[]): HTMLElement {
    return createDataTable<PendenciaRow>({
      title,
      eyebrow: isLoading ? 'Carregando…' : `${rows.length} registro${rows.length === 1 ? '' : 's'}`,
      rows: loadError || isLoading ? [] : rows,
      emptyMessage: loadError ? 'Não foi possível carregar pendências.' : 'Nenhuma pendência encontrada.',
      state: isLoading ? 'loading' : loadError ? 'error' : 'ready',
      stateTitle: loadError ? 'Não foi possível carregar pendências' : 'Nenhuma pendência encontrada',
      errorAction: { label: 'Tentar novamente', onClick: () => void loadAll() },
      onRowClick: (item) => navigateTo(`/pendencias?selecionada=${item.id}`),
      columns: [
        { key: 'titulo', label: 'Pendência' },
        { key: 'vinculacao', label: 'Vinculação', render: (item) => vinculacaoLabel(item) },
        { key: 'prioridade', label: 'Prioridade', render: (item) => createStatusBadge(prioridadeLabel(item.prioridade), prioridadeTone(item.prioridade) as StatusTone) },
        { key: 'status', label: 'Status', render: (item) => createStatusBadge(statusLabel(item.status), statusTone(item.status)) }
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
