import { createClientCard, type ClientFormData } from '../components/ClientCard';
import { createClientDocumentsPanel } from '../components/ClientDocumentsPanel';
import { createDashboardCards } from '../components/DashboardCards';
import { createDataTable } from '../components/DataTable';
import { createDetailHeader } from '../components/DetailHeader';
import { createElement } from '../dom';
import { useGlobalLoading } from '../hooks/useGlobalLoading';
import { useToast } from '../hooks/useToast';
import { createBaseLayout } from '../layouts/BaseLayout';
import {
  createClient,
  deleteClient,
  getClientMetrics,
  getClients,
  updateClient,
  type ClientRow
} from '../services/clientsService';
import { getAvailablePlants, type PlantRow } from '../services/plantService';

type ClientTableRow = {
  id: number;
  nome: string;
  cpf: string;
  qtdUc: string;
  usina: string;
  status: string;
};

export function createClientsPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const toast = useToast();
  const loading = useGlobalLoading();
  let clients: ClientRow[] = [];
  let availablePlants: PlantRow[] = [];
  let selectedClientId: number | null = null;
  let searchTerm = '';
  let loadError = false;

  const layout = createBaseLayout({
    content,
    eyebrow: 'Clientes',
    title: 'Gerenciamento de clientes'
  });

  loadClients();

  return layout;

  async function loadClients(): Promise<void> {
    loading.show();
    try {
      [clients, availablePlants] = await Promise.all([getClients(), getAvailablePlants()]);
      loadError = false;
    } catch {
      loadError = true;
      toast.error('Nao foi possivel carregar clientes. Verifique se o backend esta rodando.');
    } finally {
      loading.hide();
      renderContent();
    }
  }

  function filteredClients(): ClientRow[] {
    const term = searchTerm.trim().toLowerCase();
    if (!term) return clients;

    return clients.filter((client) => {
      const haystack = [client.nome, client.cpf, client.uc, ...client.ucs.map((uc) => uc.codigo)]
        .join(' ')
        .toLowerCase();
      return haystack.includes(term);
    });
  }

  function toTableRows(): ClientTableRow[] {
    return filteredClients().map((client) => ({
      id: client.id,
      nome: client.nome,
      cpf: client.cpf,
      qtdUc: String(client.ucs.length),
      usina: client.usina || 'A definir',
      status: client.status
    }));
  }

  function renderContent(): void {
    const selectedClient = clients.find((item) => item.id === selectedClientId) ?? null;
    content.replaceChildren(selectedClient ? renderDetailView(selectedClient) : renderListView());
  }

  function renderListView(): HTMLElement {
    const fragment = createElement('div', { className: 'content-stack' });
    const pageActions = createElement('div', { className: 'page-actions' });
    const searchInput = createElement('input');
    const newClientButton = createElement('button', { textContent: '+ Novo Cliente', type: 'button' });
    const table = createDataTable<ClientTableRow>({
      title: 'Lista de clientes',
      eyebrow: 'Clientes',
      rows: toTableRows(),
      emptyMessage: loadError ? 'Nao foi possivel carregar clientes.' : 'Nenhum cliente encontrado.',
      onRowClick: (row) => {
        selectedClientId = row.id;
        renderContent();
      },
      columns: [
        { key: 'nome', label: 'Nome' },
        { key: 'cpf', label: 'CPF / CNPJ' },
        { key: 'qtdUc', label: 'Qtd. UC' },
        { key: 'usina', label: 'Usina principal' },
        { key: 'status', label: 'Status' }
      ]
    });

    searchInput.type = 'text';
    searchInput.placeholder = 'Pesquisar cliente, CPF, UC...';
    searchInput.value = searchTerm;
    searchInput.addEventListener('input', () => {
      searchTerm = searchInput.value;
      renderContent();
    });

    newClientButton.addEventListener('click', () => openClientEditor(null));
    pageActions.append(searchInput, newClientButton);

    fragment.append(createDashboardCards(getClientMetrics(clients)), pageActions, table);
    return fragment;
  }

  function renderDetailView(client: ClientRow): HTMLElement {
    const view = createElement('div', { className: 'detail-view' });
    const editButton = createElement('button', { className: 'secondary-button', textContent: 'Editar', type: 'button' });
    const deleteButton = createElement('button', { className: 'danger-button', textContent: 'Excluir', type: 'button' });

    editButton.addEventListener('click', () => openClientEditor(client));
    deleteButton.addEventListener('click', () => confirmDeleteClient(client));

    const header = createDetailHeader({
      backLabel: 'Clientes',
      onBack: () => {
        selectedClientId = null;
        renderContent();
      },
      title: client.nome,
      badge: createStatusBadge(client.status),
      actions: [editButton, deleteButton]
    });

    const info = createElement('div', { className: 'info-grid' });
    info.append(
      createInfoItem('CPF / CNPJ', client.cpf),
      createInfoItem('Email', client.email || '-'),
      createInfoItem('Telefone', client.telefone || '-'),
      createInfoItem('Concessionaria', client.concessionaria || '-')
    );

    const ucSectionTitle = createElement('div', { className: 'detail-section-title' });
    ucSectionTitle.appendChild(createElement('h3', { textContent: `Unidades consumidoras (${client.ucs.length})` }));

    const ucList = createElement('div');
    if (client.ucs.length === 0) {
      ucList.appendChild(createElement('p', { className: 'empty-state small', textContent: 'Nenhuma UC vinculada ainda.' }));
    } else {
      client.ucs.forEach((uc) => ucList.appendChild(createUcSummaryCard(uc)));
    }

    view.append(header, info, ucSectionTitle, ucList, createClientDocumentsPanel(client.id));
    return view;
  }

  function createUcSummaryCard(uc: ClientRow['ucs'][number]): HTMLElement {
    const card = createElement('article', { className: 'uc-summary-card' });
    const head = createElement('div', { className: 'uc-summary-head' });
    const title = createElement('strong', { textContent: uc.apelido ? `${uc.codigo} (${uc.apelido})` : uc.codigo || 'UC sem codigo' });

    head.append(title, createStatusBadge(uc.conexoes.length > 0 ? 'Conectada' : 'Sem usina'));

    const grid = createElement('div', { className: 'uc-summary-grid' });
    grid.append(
      createInfoItem('Consumo', uc.consumo || '-'),
      createInfoItem('Tarifa', uc.baseTarifaria),
      createInfoItem('Desconto', uc.desconto ? `${uc.desconto}%` : '-'),
      createInfoItem('Ligacao', uc.tipoLigacao)
    );

    card.append(head, grid);

    if (uc.conexoes.length > 0) {
      const connections = createElement('div');
      uc.conexoes.forEach((conexao) => {
        connections.appendChild(createElement('span', {
          className: 'uc-connection-tag',
          textContent: `${conexao.usina} · ${conexao.percentual}%`
        }));
      });
      card.appendChild(connections);
    }

    return card;
  }

  function createInfoItem(label: string, value: string): HTMLElement {
    const item = createElement('div', { className: 'info-item' });
    item.append(
      createElement('span', { className: 'info-label', textContent: label }),
      createElement('span', { className: 'info-value', textContent: value })
    );
    return item;
  }

  function createStatusBadge(status: string): HTMLElement {
    const normalized = status.toLowerCase();
    let tone = 'tone-warning';

    if (normalized.includes('conclu') || normalized.includes('conectada') || normalized.includes('ativ')) tone = 'tone-success';
    if (normalized.includes('vencid') || normalized.includes('sem usina')) tone = 'tone-danger';

    return createElement('span', { className: `status-badge ${tone}`, textContent: status });
  }

  function openClientEditor(client: ClientRow | null): void {
    document.body.appendChild(createClientCard({
      client: client ?? undefined,
      availablePlants,
      onCancel: () => {
        document.querySelector('.modal-overlay')?.remove();
      },
      onSave: async (data) => {
        await saveClient(client, data);
        document.querySelector('.modal-overlay')?.remove();
        await loadClients();
      },
      onDelete: client ? () => {
        document.querySelector('.modal-overlay')?.remove();
        confirmDeleteClient(client);
      } : undefined
    }));
  }

  async function saveClient(existing: ClientRow | null, data: ClientFormData): Promise<void> {
    loading.show();
    try {
      if (existing) {
        await updateClient(existing.id, data);
        toast.success('Cliente atualizado.');
      } else {
        const created = await createClient(data);
        selectedClientId = created.id;
        toast.success('Cliente cadastrado.');
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Nao foi possivel salvar o cliente.');
    } finally {
      loading.hide();
    }
  }

  async function confirmDeleteClient(client: ClientRow): Promise<void> {
    const confirmed = window.confirm(`Excluir o cliente ${client.nome}? Essa acao remove tambem as UCs vinculadas e nao pode ser desfeita.`);
    if (!confirmed) return;

    loading.show();
    try {
      await deleteClient(client.id);
      toast.success('Cliente excluido.');
      if (selectedClientId === client.id) selectedClientId = null;
      await loadClients();
    } catch {
      toast.error('Nao foi possivel excluir o cliente.');
    } finally {
      loading.hide();
    }
  }
}