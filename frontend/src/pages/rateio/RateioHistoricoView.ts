import { createDataTable } from '../../components/DataTable';
import { createDetailDrawer } from '../../components/DetailDrawer';
import { createStatusBadge, type StatusTone } from '../../components/StatusBadge';
import { createElement } from '../../dom';
import { useToast } from '../../hooks/useToast';
import {
  getHistoricoExecucaoDetalhe, getHistoricoExecucoes,
  type RateioExecucao, type RateioExecucaoDetalhe, type RateioExecucaoUc
} from '../../services/rateioService';
import { formatDateTime } from '../../utils/date';
import { t } from '../../services/i18nService';

export type RateioHistoricoView = { element: HTMLElement; refresh: () => void };

function statusLabel(status: RateioExecucaoUc['status']): string {
  if (status === 'novo') return t('rateio.historico.statusNovo');
  if (status === 'alterado') return t('rateio.historico.statusAlterado');
  return t('rateio.historico.statusIgual');
}
const STATUS_TONE: Record<RateioExecucaoUc['status'], StatusTone> = {
  novo: 'info', alterado: 'warning', igual: 'neutral'
};

export function createRateioHistoricoView(): RateioHistoricoView {
  const element = createElement('section', { className: 'content-stack' });
  const toast = useToast();
  let execucoes: RateioExecucao[] = [];
  let isLoading = true;
  let loadError = false;
  let abertura: { lote: string; detalhe: RateioExecucaoDetalhe | null; loading: boolean; error: boolean } | null = null;

  load();
  render();
  return { element, refresh: load };

  function load(): void {
    isLoading = true;
    loadError = false;
    render();
    void getHistoricoExecucoes()
      .then((data) => { execucoes = data; })
      .catch(() => { loadError = true; toast.error(t('rateio.historico.loadError')); })
      .finally(() => { isLoading = false; render(); });
  }

  function abrirExecucao(lote: string): void {
    abertura = { lote, detalhe: null, loading: true, error: false };
    render();
    void getHistoricoExecucaoDetalhe(lote)
      .then((detalhe) => { if (abertura?.lote === lote) abertura = { lote, detalhe, loading: false, error: false }; })
      .catch(() => { if (abertura?.lote === lote) abertura = { lote, detalhe: null, loading: false, error: true }; toast.error(t('rateio.historico.detailLoadError')); })
      .finally(() => render());
  }

  function render(): void {
    const table = createDataTable<RateioExecucao>({
      title: t('rateio.historico.title'),
      eyebrow: t('rateio.historico.eyebrow'),
      rows: execucoes,
      state: isLoading ? 'loading' : loadError ? 'error' : execucoes.length ? 'ready' : 'empty',
      stateTitle: loadError ? t('rateio.historico.stateTitleError') : t('rateio.historico.stateTitleEmpty'),
      emptyMessage: t('rateio.historico.emptyMessage'),
      errorAction: { label: t('rateio.historico.retry'), onClick: load },
      onRowClick: (execucao) => abrirExecucao(execucao.lote),
      columns: [
        { key: 'criadoEm', label: t('rateio.historico.columnData'), render: (row) => formatDateTime(row.criadoEm) },
        { key: 'usinaNome', label: t('rateio.historico.columnUsina'), render: (row) => row.usinaNome ?? t('rateio.historico.usinaRemovida') },
        { key: 'competencia', label: t('rateio.historico.columnCompetencia') },
        { key: 'quantidadeUcs', label: t('rateio.historico.columnUcs'), align: 'right', render: (row) => String(row.quantidadeUcs) }
      ]
    });

    const blocks: HTMLElement[] = [table];
    if (abertura) blocks.push(renderDrawer(abertura));
    element.replaceChildren(...blocks);
  }

  function renderDrawer(estado: { lote: string; detalhe: RateioExecucaoDetalhe | null; loading: boolean; error: boolean }): HTMLElement {
    const detalhe = estado.detalhe;
    const titulo = detalhe ? `${detalhe.usinaNome ?? t('rateio.historico.usinaRemovida')} — ${detalhe.competencia}` : t('rateio.historico.drawerDefaultTitle');

    const body = createElement('div', { className: 'content-stack' });
    if (estado.loading) {
      body.appendChild(createElement('p', { className: 'loading-state', textContent: t('rateio.historico.loading') }));
    } else if (estado.error || !detalhe) {
      body.appendChild(createElement('p', { className: 'empty-state small', textContent: t('rateio.historico.drawerError') }));
    } else {
      body.append(renderResumo(detalhe), renderUcsTable(detalhe));
    }

    return createDetailDrawer({
      title: titulo,
      onClose: () => { abertura = null; render(); },
      tabs: [{ label: t('rateio.historico.tabAplicado'), content: body }]
    });
  }

  function renderResumo(detalhe: RateioExecucaoDetalhe): HTMLElement {
    const resumo = createElement('p', { className: 'rateio-historico-resumo' });
    resumo.textContent = `${t('rateio.historico.resumoPrefix')} ${formatDateTime(detalhe.criadoEm)}. ${
      detalhe.temExecucaoAnterior
        ? t('rateio.historico.resumoComparado')
        : t('rateio.historico.resumoPrimeira')
    }`;
    return resumo;
  }

  function renderUcsTable(detalhe: RateioExecucaoDetalhe): HTMLElement {
    return createDataTable<RateioExecucaoUc>({
      title: t('rateio.historico.ucsTableTitle'),
      eyebrow: t('rateio.historico.ucsTableEyebrow'),
      rows: detalhe.ucs,
      state: 'ready',
      emptyMessage: t('rateio.historico.ucsTableEmpty'),
      storageKey: 'rateio-historico-execucao-ucs',
      columns: [
        { key: 'ucCodigo', label: t('rateio.historico.columnUc'), render: (row) => row.ucCodigo ?? `#${row.ucId}` },
        { key: 'percentualAnterior', label: t('rateio.historico.columnPercentualAnterior'), align: 'right', render: (row) => row.percentualAnterior === null ? '—' : `${row.percentualAnterior}%` },
        { key: 'percentual', label: t('rateio.historico.columnPercentualAtual'), align: 'right', render: (row) => `${row.percentual}%` },
        { key: 'status', label: t('rateio.historico.columnSituacao'), render: (row) => createStatusBadge(statusLabel(row.status), STATUS_TONE[row.status]) }
      ]
    });
  }
}
