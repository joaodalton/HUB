import { createClientCard, type ClientFormData } from '../components/ClientCard';
import { createDashboardCards } from '../components/DashboardCards';
import { createDataTable } from '../components/DataTable';
import { createElement } from '../dom';
import { useToast } from '../hooks/useToast';
import { createBaseLayout } from '../layouts/BaseLayout';
import {
  createClient,
  deleteClient,
  getAvailablePlants,
  getClientMetrics,
  getClients,
  type ClientRow,
  updateClient
} from '../services/operationsService';

export function createClientsPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const toast = useToast();
  let selectedClient: ClientRow | null = null;
  let isCreating = false;

  renderContent();

  return createBaseLayout({
    content,
    eyebrow: 'Clientes',
    title: 'Acompanhe clientes, UCs vinculadas e status operacional'
  });

  function renderContent(): void {
    const pageActions = createElement('div', { className: 'page-actions' });
    const newClientButton = createElement('button', { textContent: 'Novo cliente', type: 'button' });
    const table = createDataTable<ClientRow>({
      title: 'Clientes cadastrados',
      eyebrow: 'Listagem',
      rows: getClients(),
      emptyMessage: 'Nenhum cliente cadastrado ainda.',
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
    const blocks: HTMLElement[] = [createDashboardCards(getClientMetrics()), pageActions];

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
      availablePlants: getAvailablePlants(),
      onCancel: () => {
        selectedClient = null;
        isCreating = false;
        renderContent();
      },
      onSave: (data) => {
        saveClient(data);
        selectedClient = null;
        isCreating = false;
        renderContent();
      },
      onDelete: selectedClient ? () => {
        const confirmed = window.confirm(`Excluir o cliente ${selectedClient?.nome}? Essa acao nao pode ser desfeita.`);

        if (!confirmed || !selectedClient) return;

        deleteClient(selectedClient.id);
        toast.success('Cliente excluido.');
        selectedClient = null;
        renderContent();
      } : undefined
    });
  }

  function saveClient(data: ClientFormData): void {
    const payload = {
      nome: data.nome,
      cpf: data.cpf,
      email: data.email,
      uc: data.ucs[0]?.codigo ?? '',
      usina: selectedClient?.usina ?? 'A definir',
      consumo: data.ucs[0]?.consumo ?? '',
      concessionaria: data.concessionaria,
      documentos: data.documentos,
      ucs: data.ucs
    };

    if (selectedClient) {
      updateClient(selectedClient.id, payload);
      toast.success('Cliente atualizado.');
      return;
    }

    createClient(payload);
    toast.success('Cliente cadastrado.');
  }
}
