// frontend/src/pages/PendenciasPage.ts
import { createElement } from '../dom';
import { useGlobalLoading } from '../hooks/useGlobalLoading';
import { useToast } from '../hooks/useToast';
import { createBaseLayout } from '../layouts/BaseLayout';
import { getClients } from '../services/clientsService';
import { getPendencias, getPendenciaResumo, verificarPendencias, type PendenciaTipo } from '../services/pendenciasService';
import { getExtraCategorias } from '../services/pendenciaCategoriasService';
import { getPlants } from '../services/plantService';
import { getUcs } from '../services/ucsService';
import { getUsers } from '../services/userService';
import { readListParam, readPositiveListParam } from '../services/listState';
import { renderListView } from './pendencias/PendenciasListView';
import { renderDetailPanel } from './pendencias/PendenciasDetailPanel';
import { openPendenciaEditor } from './pendencias/PendenciasEditorModal';
import type { PendenciasContext, PendenciasState } from './pendencias/shared';

export function createPendenciasPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const toast = useToast();
  const loading = useGlobalLoading();

  // Agenda navega com uma dica de seleção; a lista ainda busca e autoriza o
  // registro pelo endpoint normal antes de mostrá-lo.
  const requestedId = Number(readListParam('selecionada'));

  const state: PendenciasState = {
    pendencias: [],
    resumo: { pendencias: 0, alertas: 0, erros: 0 },
    clients: [],
    ucs: [],
    plants: [],
    users: [],
    categoriaExtras: [],
    loadError: false,
    isLoading: true,
    selectedId: Number.isSafeInteger(requestedId) && requestedId > 0 ? requestedId : null,
    tipoFilter: (readListParam('tipo') as PendenciaTipo) ?? null,
    showAll: readListParam('todas') === 'true',
    searchTerm: readListParam('busca') ?? '',
    page: readPositiveListParam('pagina')
  };

  const ctx: PendenciasContext = {
    state,
    toast,
    loading,
    loadAll,
    renderContent,
    openPendenciaEditor: (pendencia) => openPendenciaEditor(ctx, pendencia)
  };

  const layout = createBaseLayout({
    content,
    eyebrow: 'Operação',
    title: 'Pendências',
    description: 'Central de ações do HUB para pendências, alertas e erros.'
  });

  let verificacaoEmAndamento = false;

  renderContent();
  void loadAll();

  // Polling periodico: reaproveita a mesma verificacao automatica do load
  // inicial, pra pegar pendencia/alerta criado por outro processo enquanto
  // a tela fica aberta. O router nunca desmonta paginas (so troca o
  // conteudo do root) -- sem isso o interval ficaria rodando pra sempre em
  // segundo plano apos navegar pra outra tela. `popstate` dispara em toda
  // navegacao real (Sidebar/voltar do navegador; ver router.ts/Sidebar.ts),
  // nunca em filtro/paginacao internos (writeListState so usa pushState).
  const pollId = window.setInterval(() => { void runVerificacaoAutomatica(); }, 60000);
  window.addEventListener('popstate', () => window.clearInterval(pollId), { once: true });

  return layout;

  async function loadAll(): Promise<void> {
    state.isLoading = true;
    loading.show();
    try {
      const [pendenciasData, resumoData, clientsData, ucsData, plantsData, usersData, categoriaExtrasData] = await Promise.all([
        getPendencias(),
        getPendenciaResumo(),
        getClients(),
        getUcs(),
        getPlants(),
        getUsers(),
        getExtraCategorias()
      ]);
      state.pendencias = pendenciasData;
      state.resumo = resumoData;
      state.clients = clientsData;
      state.ucs = ucsData;
      state.plants = plantsData;
      state.users = usersData;
      state.categoriaExtras = categoriaExtrasData;
      state.loadError = false;
    } catch {
      state.loadError = true;
      toast.error('Não foi possível carregar pendências. Verifique se o backend está rodando.');
    } finally {
      state.isLoading = false;
      loading.hide();
      renderContent();
    }

    // Verificacao automatica roda DEPOIS, fora do try/finally do loading
    // global -- nunca acende o overlay e nunca chama loadAll() de novo
    // (isso causava um ciclo show/hide sem fim quando o backend sempre
    // encontrava algo pra criar/resolver, dando a impressao de "carregando
    // pra sempre" no canto superior direito).
    void runVerificacaoAutomatica();
  }

  async function runVerificacaoAutomatica(): Promise<void> {
    if (verificacaoEmAndamento) return;
    verificacaoEmAndamento = true;

    try {
      const resultado = await verificarPendencias();

      if (resultado.total_criadas > 0) {
        toast.success(`${resultado.total_criadas} nova(s) pendência(s) criada(s) automaticamente.`);
        await refreshListaSemLoading();
      } else if (resultado.resolvidas > 0) {
        toast.success(`${resultado.resolvidas} pendência(s) resolvida(s) automaticamente.`);
        await refreshListaSemLoading();
      }
    } catch {
      // Silencioso - não mostra erro na verificação automática
    } finally {
      verificacaoEmAndamento = false;
    }
  }

  // Atualiza só pendências + resumo (sem loading global, sem recarregar
  // clientes/UCs/usinas de novo) -- usado depois da verificação automática.
  async function refreshListaSemLoading(): Promise<void> {
    try {
      const [pendenciasData, resumoData] = await Promise.all([getPendencias(), getPendenciaResumo()]);
      state.pendencias = pendenciasData;
      state.resumo = resumoData;
    } catch {
      // mantém o que já estava carregado se falhar
    } finally {
      renderContent();
    }
  }

  function renderContent(): void {
    const selected = state.pendencias.find((item) => item.id === state.selectedId) ?? null;

    if (!selected) {
      content.replaceChildren(renderListView(ctx));
      return;
    }

    const layoutWrap = createElement('div', { className: 'pendencias-layout' });
    layoutWrap.append(renderListView(ctx), renderDetailPanel(ctx, selected));
    content.replaceChildren(layoutWrap);
  }
}
