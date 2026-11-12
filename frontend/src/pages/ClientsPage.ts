import { createClientCard, type ClientFormData } from '../components/ClientCard';
import { createClientDetailView, createClientPlantsPanel, createClientUcPanel } from '../components/ClientDetailView';
import { createClientDocumentsPanel } from '../components/ClientDocumentsPanel';
import { createDashboardCards } from '../components/DashboardCards';
import { createDataTable } from '../components/DataTable';
import { createDetailDrawer } from '../components/DetailDrawer';
import { createImportacoesModal } from '../components/ImportacoesModal';
import { createElement } from '../dom';
import { useGlobalLoading } from '../hooks/useGlobalLoading';
import { useToast } from '../hooks/useToast';
import { createBaseLayout } from '../layouts/BaseLayout';
import { getAvailablePlants, type PlantRow } from '../services/plantService';
import {
  createClient,
  deleteClient,
  getClientMetrics,
  getClients,
  type ClientRow,
  updateClient
} from '../services/clientsService';
import { createDebouncedInput, matchesListSearch, pageSlice, readListParam, readPositiveListParam, writeListState } from '../services/listState';
import { t } from '../services/i18nService';

const PAGE_SIZE = 25;

function clientStatusLabel(status: string): string {
  return ({
    Ativo: t('clients.status.ativo'),
    'Esperando usina': t('clients.status.esperandoUsina'),
    'Esperando rateio': t('clients.status.esperandoRateio'),
    Concluido: t('clients.status.concluido')
  } as Record<string, string>)[status] ?? status;
}

export function createClientsPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const toast = useToast();
  const loading = useGlobalLoading();
  let clients: ClientRow[] = [];
  let availablePlants: PlantRow[] = [];
 let selectedClient: ClientRow | null = null;
  const requestedClientId = Number(readListParam('selecionada'));
  let viewingClient: ClientRow | null = null;
  let searchTerm = readListParam('busca') ?? '';
  let page = readPositiveListParam('pagina');
  let isCreating = false;
  let loadError = false;
  let isLoading = true;

  const layout = createBaseLayout({
    content,
    eyebrow: t('clients.page.eyebrow'),
    title: t('clients.page.title'),
    description: t('clients.page.description')
  });

 const search = createElement('input');
 search.type = 'search'; search.placeholder = t('clients.search.placeholder'); search.setAttribute('aria-label', t('clients.search.ariaLabel'));
 const applySearch = createDebouncedInput((value) => { if (value !== searchTerm) { searchTerm = value; page = 1; writeListState({ busca: value || null, pagina: null, selecionada: null }); viewingClient = null; renderContent(); } });
 search.addEventListener('input', () => applySearch(search.value));
 const filters = createElement('div', { className: 'page-actions' }); filters.appendChild(search);

 const pageActions = createElement('div', { className: 'page-actions' });
 const newClientButton = createElement('button', { textContent: t('clients.actions.new'), type: 'button' });
 const importButton = createElement('button', { className: 'secondary-button', textContent: t('clients.actions.import'), type: 'button' });
 newClientButton.addEventListener('click', () => { selectedClient = null; isCreating = true; renderContent(); });
 importButton.addEventListener('click', () => document.body.appendChild(createImportacoesModal(() => void loadClients())));
 pageActions.append(importButton, newClientButton);
 const dashboardHost = createElement('div');
 const editorHost = createElement('div');
 const tableHost = createElement('div');
 const paginationHost = createElement('div');
 const drawerHost = createElement('div');
 let renderedEditorKey: ClientRow | 'new' | null = null;
 let renderedDrawerClient: ClientRow | null = null;
 content.replaceChildren(pageActions, filters, dashboardHost, editorHost, tableHost, paginationHost, drawerHost);

  renderContent();
  loadClients();

  return layout;

  async function loadClients(): Promise<void> {
    isLoading = true;
    loading.show();
    try {
      [clients, availablePlants] = await Promise.all([getClients(), getAvailablePlants()]);
      if (Number.isSafeInteger(requestedClientId) && requestedClientId > 0) viewingClient = clients.find((client) => client.id === requestedClientId) ?? null;
      loadError = false;
    } catch {
      loadError = true;
      toast.error(t('clients.toast.loadError'));
    } finally {
      isLoading = false;
      loading.hide();
      renderContent();
    }
  }

 function renderContent(): void {
    const filteredClients = clients.filter((client) => matchesListSearch(searchTerm, `${client.nome} ${client.cpf} ${client.email} ${client.uc} ${client.usina} ${client.status}`));
    const paged = pageSlice(filteredClients, page, PAGE_SIZE);
    page = paged.page;
    const table = createDataTable<ClientRow>({
      title: t('clients.table.title'),
      eyebrow: t('clients.table.eyebrow'),
      rows: paged.rows,
      emptyMessage: loadError ? t('clients.table.loadError') : t('clients.table.empty'),
      state: isLoading ? 'loading' : loadError ? 'error' : searchTerm ? 'filtered' : 'ready',
      stateTitle: loadError ? t('clients.table.stateTitleError') : searchTerm ? t('clients.table.stateTitleFiltered') : t('clients.table.stateTitleEmpty'),
      emptyAction: { label: t('clients.actions.clearFilters'), onClick: () => { searchTerm = ''; page = 1; writeListState({ busca: null, pagina: null }); renderContent(); } },
      errorAction: { label: t('common.retry'), onClick: () => void loadClients() },
      onRowClick: (client) => {
        viewingClient = client;
        writeListState({ selecionada: client.id });
        renderContent();
      },
      columns: [
        { key: 'nome', label: t('clients.columns.name') },
        { key: 'uc', label: t('clients.columns.uc') },
        { key: 'usina', label: t('clients.columns.plant') },
        { key: 'consumo', label: t('clients.columns.consumption'), align: 'right' },
        { key: 'status', label: t('clients.columns.status'), render: (client) => clientStatusLabel(client.status) },
        { key: 'cpf', label: t('clients.columns.cpf'), defaultVisible: false },
        { key: 'email', label: t('clients.columns.email'), defaultVisible: false },
        { key: 'telefone', label: t('clients.columns.phone'), defaultVisible: false, render: (client) => client.telefone || t('clients.notInformed') },
        { key: 'concessionaria', label: t('clients.columns.utility'), defaultVisible: false },
        { key: 'dataNascimento', label: t('clients.columns.birthDate'), defaultVisible: false, render: (client) => formatClientBirthDate(client.dataNascimento) }
      ]
    });
    if (search.value !== searchTerm) search.value = searchTerm;
    dashboardHost.replaceChildren(createDashboardCards(getClientMetrics(clients)));
    tableHost.replaceChildren(table);
    paginationHost.replaceChildren(createPagination(page, paged.pages, filteredClients.length, (nextPage) => { page = nextPage; writeListState({ pagina: page }); renderContent(); }));

    const editorKey = selectedClient ?? (isCreating ? 'new' as const : null);
    if (editorKey !== renderedEditorKey) {
      renderedEditorKey = editorKey;
      editorHost.replaceChildren(...(isCreating || selectedClient ? [createClientEditor()] : []));
    }
    if (viewingClient !== renderedDrawerClient) {
      renderedDrawerClient = viewingClient;
      drawerHost.replaceChildren(...(viewingClient ? [createClientDrawer(viewingClient)] : []));
    }
  }

  function createClientEditor(): HTMLElement {
    const editingClientId = selectedClient?.id;

    return createClientCard({
      client: selectedClient ?? undefined,
      availablePlants,
      onCancel: () => {
        selectedClient = null;
        isCreating = false;
        renderContent();
      },
      onSave: async (data) => {
        await saveClient(data);
        selectedClient = null;
        isCreating = false;
        await loadClients();

        // Se estava editando o cliente que a pagina de detalhes esta mostrando,
        // atualiza a visualizacao com o dado novo em vez de voltar pra lista.
        if (editingClientId) {
          viewingClient = clients.find((client) => client.id === editingClientId) ?? null;
        }

        renderContent();
      },
      onDelete: selectedClient ? async () => {
        const confirmed = window.confirm(`${t('clients.confirmDelete.prefix')} ${selectedClient?.nome}${t('clients.confirmDelete.suffix')}`);

        if (!confirmed || !selectedClient) return;

        loading.show();
        try {
          await deleteClient(selectedClient.id);
          toast.success(t('clients.toast.deleted'));
          selectedClient = null;
          await loadClients();
        } catch {
          toast.error(t('clients.toast.deleteError'));
        } finally {
          loading.hide();
        }
      } : undefined
    });
  }

  function createClientDrawer(client: ClientRow): HTMLElement {
    const openEditor = () => {
      selectedClient = client;
      viewingClient = null;
      renderContent();
    };
    return createDetailDrawer({
      title: client.nome,
      onClose: () => { viewingClient = null; writeListState({ selecionada: null }, 'replace'); renderContent(); },
      tabs: [
        { label: t('clients.drawer.tabOverview'), content: createClientDetailView({ client, onEdit: openEditor, onDelete: () => handleDeleteFromDetail(client) }) },
        { label: t('clients.drawer.tabUcs'), content: createClientUcPanel(client, openEditor) },
        { label: t('clients.drawer.tabPlants'), content: createClientPlantsPanel(client) },
        { label: t('clients.drawer.tabDocuments'), content: createClientDocumentsPanel(client.id) }
      ]
    });
  }

  async function handleDeleteFromDetail(client: ClientRow): Promise<void> {
    const confirmed = window.confirm(`${t('clients.confirmDelete.prefix')} ${client.nome}${t('clients.confirmDelete.suffix')}`);
    if (!confirmed) return;

    loading.show();
    try {
      await deleteClient(client.id);
      toast.success(t('clients.toast.deleted'));
      viewingClient = null;
      await loadClients();
    } catch {
      toast.error(t('clients.toast.deleteError'));
    } finally {
      loading.hide();
    }
  }

  async function saveClient(data: ClientFormData): Promise<void> {
    loading.show();
    try {
      const payload = {
        nome: data.nome,
        cpf: data.cpf,
        email: data.email,
        telefone: data.telefone,
        dataNascimento: data.dataNascimento || null,
        concessionaria: data.concessionaria,
        ucs: data.ucs
      };  


      if (selectedClient) {
        await updateClient(selectedClient.id, payload);
        toast.success(t('clients.toast.updated'));
      } else {
        await createClient(payload);
        toast.success(t('clients.toast.created'));
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('clients.toast.saveError'));
    } finally {
      loading.hide();
    }
  }
}

// Split-based, sem Date() -- mesmo motivo documentado em ClientDetailView.ts
// (evita o bug de "um dia antes" por causa de fuso horario).
function formatClientBirthDate(value: string | null): string {
  if (!value) return t('clients.notInformed');
  const [year, month, day] = value.split('-');
  return `${day}/${month}/${year}`;
}

function createPagination(page: number, pages: number, total: number, onPage: (page: number) => void): HTMLElement {
  const nav = createElement('nav', { className: 'faturas-pagination pagination-left' });
  const previous = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('clients.pagination.previous') });
  previous.disabled = page <= 1;
  previous.addEventListener('click', () => onPage(page - 1));
  const next = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('clients.pagination.next') });
  next.disabled = page >= pages || total === 0;
  next.addEventListener('click', () => onPage(page + 1));
  nav.append(previous, createElement('span', { textContent: `${total ? page : 0} ${t('clients.pagination.of')} ${total ? pages : 0}` }), next);
  return nav;
}
