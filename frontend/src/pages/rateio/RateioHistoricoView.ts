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

export type RateioHistoricoView = { element: HTMLElement; refresh: () => void };

const STATUS_LABEL: Record<RateioExecucaoUc['status'], string> = {
  novo: 'Novo', alterado: 'Alterado', igual: 'Igual'
};
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
      .catch(() => { loadError = true; toast.error('Nao foi possivel carregar o historico de rateio.'); })
      .finally(() => { isLoading = false; render(); });
  }

  function abrirExecucao(lote: string): void {
    abertura = { lote, detalhe: null, loading: true, error: false };
    render();
    void getHistoricoExecucaoDetalhe(lote)
      .then((detalhe) => { if (abertura?.lote === lote) abertura = { lote, detalhe, loading: false, error: false }; })
      .catch(() => { if (abertura?.lote === lote) abertura = { lote, detalhe: null, loading: false, error: true }; toast.error('Nao foi possivel carregar essa execucao de rateio.'); })
      .finally(() => render());
  }

  function render(): void {
    const table = createDataTable<RateioExecucao>({
      title: 'Historico de rateio',
      eyebrow: 'Execucoes',
      rows: execucoes,
      state: isLoading ? 'loading' : loadError ? 'error' : execucoes.length ? 'ready' : 'empty',
      stateTitle: loadError ? 'Nao foi possivel carregar o historico' : 'Nenhum rateio aplicado ainda',
      emptyMessage: 'Nenhum rateio aplicado ainda. Toda vez que o rateio for aplicado ou confirmado numa usina, a execucao aparece aqui.',
      errorAction: { label: 'Tentar novamente', onClick: load },
      onRowClick: (execucao) => abrirExecucao(execucao.lote),
      columns: [
        { key: 'criadoEm', label: 'Data e horario', render: (row) => formatDateTime(row.criadoEm) },
        { key: 'usinaNome', label: 'Usina', render: (row) => row.usinaNome ?? 'Usina removida' },
        { key: 'competencia', label: 'Competencia' },
        { key: 'quantidadeUcs', label: 'UCs', align: 'right', render: (row) => String(row.quantidadeUcs) }
      ]
    });

    const blocks: HTMLElement[] = [table];
    if (abertura) blocks.push(renderDrawer(abertura));
    element.replaceChildren(...blocks);
  }

  function renderDrawer(estado: { lote: string; detalhe: RateioExecucaoDetalhe | null; loading: boolean; error: boolean }): HTMLElement {
    const detalhe = estado.detalhe;
    const titulo = detalhe ? `${detalhe.usinaNome ?? 'Usina removida'} — ${detalhe.competencia}` : 'Execucao de rateio';

    const body = createElement('div', { className: 'content-stack' });
    if (estado.loading) {
      body.appendChild(createElement('p', { className: 'loading-state', textContent: 'Carregando...' }));
    } else if (estado.error || !detalhe) {
      body.appendChild(createElement('p', { className: 'empty-state small', textContent: 'Nao foi possivel carregar essa execucao.' }));
    } else {
      body.append(renderResumo(detalhe), renderUcsTable(detalhe));
    }

    return createDetailDrawer({
      title: titulo,
      onClose: () => { abertura = null; render(); },
      tabs: [{ label: 'Rateio aplicado', content: body }]
    });
  }

  function renderResumo(detalhe: RateioExecucaoDetalhe): HTMLElement {
    const resumo = createElement('p', { className: 'rateio-historico-resumo' });
    resumo.textContent = `Aplicado em ${formatDateTime(detalhe.criadoEm)}. ${
      detalhe.temExecucaoAnterior
        ? 'Comparado com a execucao anterior desta usina.'
        : 'Primeira execucao registrada para esta usina -- todas as UCs aparecem como novas.'
    }`;
    return resumo;
  }

  function renderUcsTable(detalhe: RateioExecucaoDetalhe): HTMLElement {
    return createDataTable<RateioExecucaoUc>({
      title: 'UCs nesta execucao',
      eyebrow: 'Comparativo',
      rows: detalhe.ucs,
      state: 'ready',
      emptyMessage: 'Nenhuma UC nesta execucao.',
      storageKey: 'rateio-historico-execucao-ucs',
      columns: [
        { key: 'ucCodigo', label: 'UC', render: (row) => row.ucCodigo ?? `#${row.ucId}` },
        { key: 'percentualAnterior', label: '% anterior', align: 'right', render: (row) => row.percentualAnterior === null ? '—' : `${row.percentualAnterior}%` },
        { key: 'percentual', label: '% atual', align: 'right', render: (row) => `${row.percentual}%` },
        { key: 'status', label: 'Situacao', render: (row) => createStatusBadge(STATUS_LABEL[row.status], STATUS_TONE[row.status]) }
      ]
    });
  }
}
