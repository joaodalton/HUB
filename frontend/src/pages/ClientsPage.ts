import { createClientCard, type ClientFormData } from '../components/ClientCard';
import { createDashboardCards } from '../components/DashboardCards';
import { createDataTable } from '../components/DataTable';
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

export function createClientsPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const toast = useToast();
  const loading = useGlobalLoading();
  let clients: ClientRow[] = [];
  let availablePlants: PlantRow[] = [];
  let selectedClient: ClientRow | null = null;
  let isCreating = false;
  let loadError = false;

  const layout = createBaseLayout({
    content,
    eyebrow: 'Clientes',
    title: 'Acompanhe clientes, UCs vinculadas e status operacional'
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

  function renderContent(): void {
    const pageActions = createElement('div', { className: 'page-actions' });
    const newClientButton = createElement('button', { textContent: 'Novo cliente', type: 'button' });
    const table = createDataTable<ClientRow>({
      title: 'Clientes cadastrados',
      eyebrow: 'Listagem',
      rows: clients,
      emptyMessage: loadError ? 'Nao foi possivel carregar clientes.' : 'Nenhum cliente cadastrado ainda.',
      onRowClick: (client) => {
        selectedClient = client;
        isCreating = false;
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
    const blocks: HTMLElement[] = [createDashboardCards(getClientMetrics(clients)), pageActions];

    newClientButton.addEventListener('click', () => {
      selectedClient = null;
      isCreating = true;
      renderContent();
    });

    pageActions.appendChild(newClientButton);

    if (isCreating || selectedClient) {
      blocks.push(createClientEditor());
    }

    blocks.push(table);
    content.replaceChildren(...blocks);
  }

  function createClientEditor(): HTMLElement {
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

  async function saveClient(data: ClientFormData): Promise<void> {
    loading.show();
    try {
      const payload = {
        nome: data.nome,
        cpf: data.cpf,
        email: data.email,
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