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

const PAGE_SIZE = 25;

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
    eyebrow: 'Gestão',
    title: 'Clientes',
    description: 'Acompanhe clientes, UCs vinculadas e status operacional.'
  });

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
      toast.error('Nao foi possivel carregar clientes. Verifique se o backend esta rodando.');
    } finally {
      isLoading = false;
      loading.hide();
      renderContent();
    }
  }

 function renderContent(): void {
    const pageActions = createElement('div', { className: 'page-actions' });
    const newClientButton = createElement('button', { textContent: 'Novo cliente', type: 'button' });
    const importButton = createElement('button', { className: 'secondary-button', textContent: 'Importação/exportação', type: 'button' });
    const filteredClients = clients.filter((client) => matchesListSearch(searchTerm, `${client.nome} ${client.cpf} ${client.email} ${client.uc} ${client.usina} ${client.status}`));
    const paged = pageSlice(filteredClients, page, PAGE_SIZE);
    page = paged.page;
    const table = createDataTable<ClientRow>({
      title: 'Clientes cadastrados',
      eyebrow: 'Listagem',
      rows: paged.rows,
      emptyMessage: loadError ? 'Nao foi possivel carregar clientes.' : 'Nenhum cliente cadastrado ainda.',
      state: isLoading ? 'loading' : loadError ? 'error' : searchTerm ? 'filtered' : 'ready',
      stateTitle: loadError ? 'Nao foi possivel carregar clientes' : searchTerm ? 'Nenhum cliente corresponde à busca' : 'Nenhum cliente cadastrado',
      emptyAction: { label: 'Limpar filtros', onClick: () => { searchTerm = ''; page = 1; writeListState({ busca: null, pagina: null }); renderContent(); } },
      errorAction: { label: 'Tentar novamente', onClick: () => void loadClients() },
      onRowClick: (client) => {
        viewingClient = client;
        writeListState({ selecionada: client.id });
        renderContent();
      },
      columns: [
        { key: 'nome', label: 'Nome' },
        { key: 'uc', label: 'UC' },
        { key: 'usina', label: 'Usina' },
        { key: 'consumo', label: 'Consumo', align: 'right' },
        { key: 'status', label: 'Status' }
      ]
    });
    const search = createElement('input');
    search.type = 'search'; search.placeholder = 'Buscar clientes...'; search.value = searchTerm;
    const applySearch = createDebouncedInput((value) => { if (value !== searchTerm) { searchTerm = value; page = 1; writeListState({ busca: value || null, pagina: null, selecionada: null }); viewingClient = null; renderContent(); } });
    search.addEventListener('input', () => applySearch(search.value));
    const filters = createElement('div', { className: 'page-actions' }); filters.appendChild(search);
    const blocks: HTMLElement[] = [pageActions, filters, createDashboardCards(getClientMetrics(clients)), table, createPagination(page, paged.pages, filteredClients.length, (nextPage) => { page = nextPage; writeListState({ pagina: page }); renderContent(); })];

    newClientButton.addEventListener('click', () => {
      selectedClient = null;
      isCreating = true;
      renderContent();
    });
    importButton.addEventListener('click', () => document.body.appendChild(createImportacoesModal(() => void loadClients())));

    pageActions.append(importButton, newClientButton);

    if (isCreating || selectedClient) {
      blocks.push(createClientEditor());
    }

    blocks.push(table);
    content.replaceChildren(...blocks);
    if (viewingClient) content.appendChild(createClientDrawer(viewingClient));
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
        const confirmed = window.confirm(`Excluir o cliente ${selectedClient?.nome}? Essa acao nao pode ser desfeita.`);

        if (!confirmed || !selectedClient) return;

        loading.show();
        try {
          await deleteClient(selectedClient.id);
          toast.success('Cliente excluido.');
          selectedClient = null;
          await loadClients();
        } catch {
          toast.error('Nao foi possivel excluir o cliente.');
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
        { label: 'Visão geral', content: createClientDetailView({ client, onEdit: openEditor, onDelete: () => handleDeleteFromDetail(client) }) },
        { label: 'UCs', content: createClientUcPanel(client, openEditor) },
        { label: 'Usinas', content: createClientPlantsPanel(client) },
        { label: 'Documentos', content: createClientDocumentsPanel(client.id) }
      ]
    });
  }

  async function handleDeleteFromDetail(client: ClientRow): Promise<void> {
    const confirmed = window.confirm(`Excluir o cliente ${client.nome}? Essa acao nao pode ser desfeita.`);
    if (!confirmed) return;

    loading.show();
    try {
      await deleteClient(client.id);
      toast.success('Cliente excluido.');
      viewingClient = null;
      await loadClients();
    } catch {
      toast.error('Nao foi possivel excluir o cliente.');
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
        toast.success('Cliente atualizado.');
      } else {
        await createClient(payload);
        toast.success('Cliente cadastrado.');
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Nao foi possivel salvar o cliente.');
    } finally {
      loading.hide();
    }
  }
}

function createPagination(page: number, pages: number, total: number, onPage: (page: number) => void): HTMLElement {
  const nav = createElement('nav', { className: 'faturas-pagination' });
  const previous = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Anterior' });
  previous.disabled = page <= 1;
  previous.addEventListener('click', () => onPage(page - 1));
  const next = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Próxima' });
  next.disabled = page >= pages || total === 0;
  next.addEventListener('click', () => onPage(page + 1));
  nav.append(previous, createElement('span', { textContent: `${total ? page : 0} de ${total ? pages : 0}` }), next);
  return nav;
}
