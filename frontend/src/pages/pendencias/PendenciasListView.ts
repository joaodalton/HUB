// frontend/src/pages/pendencias/PendenciasListView.ts
import { createElement } from '../../dom';
import { createIconStatCard, type IconStatCardProps } from '../../components/IconStatCard';
import { createDataTable } from '../../components/DataTable';
import { createIcon } from '../../components/Icon';
import { responsavelLabel, verificarPendencias, vinculacaoLabel, type PendenciaRow } from '../../services/pendenciasService';
import { createDebouncedInput, pageSlice, writeListState } from '../../services/listState';
import { t } from '../../services/i18nService';
import {
  compareOperationalPriority,
  createAttentionBadge,
  createPrioridadeBadge,
  createStatusDot,
  createTipoBadge,
  formatDate,
  normalize,
  PAGE_SIZE,
  type PendenciasContext
} from './shared';

function getFilteredPendencias(ctx: PendenciasContext): PendenciaRow[] {
  const { state } = ctx;
  return state.pendencias.filter((item) => {
    if (!state.showAll && item.status !== 'aberta') return false;
    if (state.tipoFilter && item.tipo !== state.tipoFilter) return false;

    if (state.searchTerm) {
      const haystack = normalize(`${item.titulo} ${item.categoria} ${item.origem} ${vinculacaoLabel(item)}`);
      if (!haystack.includes(normalize(state.searchTerm))) return false;
    }

    return true;
  }).sort(compareOperationalPriority);
}

// Mesmo truque do PlantsPage.ts: toolbar (com o campo de busca) e criada
// uma vez so, refresh() troca somente os holders de cards/tabela por baixo
// -- assim o input nunca perde foco enquanto o usuario digita.
export function renderListView(ctx: PendenciasContext): HTMLElement {
  const { state } = ctx;
  const fragment = createElement('div', { className: 'content-stack' });
  const toolbar = createElement('div', { className: 'page-actions' });

  const searchInput = createElement('input');
  searchInput.type = 'text';
  searchInput.placeholder = t('pendencias.list.searchPlaceholder');
  searchInput.value = state.searchTerm;
  const applySearch = createDebouncedInput((value) => { if (value !== state.searchTerm) { state.searchTerm = value; state.page = 1; state.selectedId = null; writeListState({ busca: value || null, pagina: null, selecionada: null }); refresh(); } });
  searchInput.addEventListener('input', () => applySearch(searchInput.value));

  const toggleAllButton = createElement('button', {
    className: state.showAll ? 'secondary-button active' : 'secondary-button',
    textContent: state.showAll ? t('pendencias.list.showingAll') : t('pendencias.list.showingOpen'),
    type: 'button'
  });
  toggleAllButton.addEventListener('click', () => {
    state.showAll = !state.showAll;
    state.page = 1; state.selectedId = null;
    writeListState({ todas: state.showAll, pagina: null, selecionada: null });
    refresh();
  });

  const spacer = createElement('div');
  spacer.style.flex = '1 0 auto';
  spacer.style.minWidth = '0';

  // Botao de verificacao automatica
  const verifyButton = createElement('button', {
    className: 'secondary-button button-with-icon',
    type: 'button',
    title: t('pendencias.list.verifyNow')
  });
  verifyButton.append(createIcon('refresh'), document.createTextNode(t('pendencias.list.verifyNow')));
  verifyButton.addEventListener('click', async () => {
    verifyButton.disabled = true;
    verifyButton.textContent = t('pendencias.list.verifying');
    try {
      const resultado = await verificarPendencias();
      if (resultado.total_criadas > 0) {
        ctx.toast.success(`${resultado.total_criadas} ${t('pendencias.page.autoCreatedSuffix')}`);
      } else if (resultado.resolvidas > 0) {
        ctx.toast.success(`${resultado.resolvidas} ${t('pendencias.page.autoResolvedSuffix')}`);
      } else {
        ctx.toast.success(t('pendencias.list.verifySuccessNone'));
      }
      await ctx.loadAll();
    } catch {
      ctx.toast.error(t('pendencias.list.verifyError'));
    } finally {
      verifyButton.disabled = false;
      verifyButton.innerHTML = '';
      verifyButton.append(createIcon('refresh'), document.createTextNode(t('pendencias.list.verifyNow')));
    }
  });

  const newButton = createElement('button', { className: 'button-with-icon', type: 'button' });
  newButton.append(createIcon('plus'), document.createTextNode(t('pendencias.list.newButton')));
  newButton.addEventListener('click', () => ctx.openPendenciaEditor(null));

  toolbar.append(verifyButton, newButton);

  const filtersRow = createElement('div', { className: 'page-actions' });
  filtersRow.append(searchInput, toggleAllButton, spacer);

  const statsHolder = createElement('div');
  const tableHolder = createElement('div');
  const paginationHolder = createElement('div');

  function refresh(): void {
    statsHolder.replaceChildren(createStatCards());
    tableHolder.replaceChildren(createPendenciasTable());
    paginationHolder.replaceChildren(createPagination());
  }

  refresh();
  fragment.append(toolbar, filtersRow, statsHolder, tableHolder, paginationHolder);
  return fragment;

  function createStatCards(): HTMLElement {
    const metrics: IconStatCardProps[] = [
      {
        label: t('pendencias.list.statFila'),
        value: String(state.resumo.pendencias),
        chipColor: 'amber',
        icon: 'pending',
        onClick: () => {
          state.tipoFilter = state.tipoFilter === 'pendencia' ? null : 'pendencia';
          state.page = 1; state.selectedId = null; writeListState({ tipo: state.tipoFilter, pagina: null, selecionada: null });
          refresh();
        }
      },
      {
        label: t('pendencias.list.statAlertas'),
        value: String(state.resumo.alertas),
        chipColor: 'amber',
        icon: 'cobrancas',
        onClick: () => {
          state.tipoFilter = state.tipoFilter === 'alerta' ? null : 'alerta';
          state.page = 1; state.selectedId = null; writeListState({ tipo: state.tipoFilter, pagina: null, selecionada: null });
          refresh();
        }
      },
      {
        label: t('pendencias.list.statErros'),
        value: String(state.resumo.erros),
        chipColor: 'red',
        icon: 'x',
        onClick: () => {
          state.tipoFilter = state.tipoFilter === 'erro' ? null : 'erro';
          state.page = 1; state.selectedId = null; writeListState({ tipo: state.tipoFilter, pagina: null, selecionada: null });
          refresh();
        }
      }
    ];

    const grid = createElement('section', { className: 'metric-grid' });
    metrics.forEach((metric) => grid.appendChild(createIconStatCard(metric)));
    return grid;
  }

  function createPendenciasTable(): HTMLElement {
    const filteredRows = getFilteredPendencias(ctx);
    const paged = pageSlice(filteredRows, state.page, PAGE_SIZE); state.page = paged.page;
    const isFiltered = Boolean(state.searchTerm || state.tipoFilter);

    return createDataTable<PendenciaRow>({
      title: t('pendencias.list.tableTitle'),
      eyebrow: t('pendencias.list.tableEyebrow'),
      rows: paged.rows,
      emptyMessage: state.loadError
        ? t('pendencias.list.emptyError')
        : isFiltered
          ? t('pendencias.list.emptyFiltered')
          : state.showAll
            ? t('pendencias.list.emptyAll')
            : t('pendencias.list.emptyOpen'),
      state: state.isLoading ? 'loading' : state.loadError ? 'error' : isFiltered ? 'filtered' : 'ready',
      stateTitle: state.loadError ? t('pendencias.list.stateTitleError') : isFiltered ? t('pendencias.list.stateTitleFiltered') : state.showAll ? t('pendencias.list.stateTitleAll') : t('pendencias.list.stateTitleOpen'),
      emptyAction: { label: t('pendencias.list.clearFilters'), onClick: () => { state.searchTerm = ''; state.tipoFilter = null; state.showAll = false; state.page = 1; writeListState({ busca: null, tipo: null, todas: null, pagina: null }); refresh(); } },
      errorAction: { label: t('pendencias.list.retry'), onClick: () => void ctx.loadAll() },
      onRowClick: (item) => {
        state.selectedId = item.id;
        writeListState({ selecionada: item.id });
        ctx.renderContent();
      },
      columns: [
        { key: 'tipo', label: t('pendencias.list.colTipo'), render: (item) => createTipoBadge(item.tipo) },
        { key: 'atencao', label: t('pendencias.list.colAtencao'), render: (item) => createAttentionBadge(item) },
        { key: 'titulo', label: t('pendencias.list.colPendencia') },
        { key: 'categoria', label: t('pendencias.list.colCategoria') },
        { key: 'origem', label: t('pendencias.list.colOrigem') },
        { key: 'vinculacao', label: t('pendencias.list.colVinculacao'), render: (item) => vinculacaoLabel(item) },
        { key: 'responsavel', label: t('pendencias.list.colResponsavel'), render: (item) => responsavelLabel(item) },
        { key: 'prazo', label: t('pendencias.list.colPrazo'), render: (item) => formatDate(item.prazo) },
        { key: 'prioridade', label: t('pendencias.list.colPrioridade'), render: (item) => createPrioridadeBadge(item.prioridade) },
        { key: 'status', label: t('pendencias.list.colStatus'), render: (item) => createStatusDot(item.status) }
      ]
    });
  }

  function createPagination(): HTMLElement {
    const rows = getFilteredPendencias(ctx); const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
    const nav = createElement('nav', { className: 'faturas-pagination' });
    const previous = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('pendencias.list.previous') });
    previous.disabled = state.page <= 1; previous.addEventListener('click', () => { state.page--; writeListState({ pagina: state.page }); refresh(); });
    const next = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('pendencias.list.next') });
    next.disabled = state.page >= pages || rows.length === 0; next.addEventListener('click', () => { state.page++; writeListState({ pagina: state.page }); refresh(); });
    nav.append(previous, createElement('span', { textContent: `${rows.length ? state.page : 0} ${t('pendencias.list.pageOf')} ${rows.length ? pages : 0}` }), next);
    return nav;
  }
}
