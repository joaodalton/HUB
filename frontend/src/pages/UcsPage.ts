import { createDashboardCards } from '../components/DashboardCards';
import { createDataTable } from '../components/DataTable';
import { createUcCard } from '../components/UcCard';
import { createElement } from '../dom';
import { useGlobalLoading } from '../hooks/useGlobalLoading';
import { useToast } from '../hooks/useToast';
import { createBaseLayout } from '../layouts/BaseLayout';
import { getClients, type ClientRow } from '../services/clientsService';
import { getAvailablePlants, type PlantRow } from '../services/plantService';
import {
  createUc,
  deleteUc,
  getUcMetrics,
  getUcs,
  type UcPayload,
  type UcRow,
  updateUc
} from '../services/ucsService';

type UcTableRow = UcRow & { cliente: string; usina: string };

export function createUcsPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const toast = useToast();
  const loading = useGlobalLoading();
  let ucs: UcRow[] = [];
  let clients: ClientRow[] = [];
  let availablePlants: PlantRow[] = [];
  let selectedUc: UcRow | null = null;
  let isCreating = false;
  let loadError = false;

  const layout = createBaseLayout({
    content,
    eyebrow: 'UCs',
    title: 'Unidades consumidoras vinculadas a clientes e usinas'
  });

  loadAll();

  return layout;

  async function loadAll(): Promise<void> {
    loading.show();
    try {
      [ucs, clients, availablePlants] = await Promise.all([getUcs(), getClients(), getAvailablePlants()]);
      loadError = false;
    } catch {
      loadError = true;
      toast.error('Nao foi possivel carregar UCs. Verifique se o backend esta rodando.');
    } finally {
      loading.hide();
      renderContent();
    }
  }

  function renderContent(): void {
    const pageActions = createElement('div', { className: 'page-actions' });
    const newUcButton = createElement('button', { textContent: 'Nova UC', type: 'button' });

    const rows: UcTableRow[] = ucs.map((uc) => ({
      ...uc,
      cliente: uc.clienteNome ?? '-',
      usina: uc.conexoes.length > 0 ? uc.conexoes.map((conexao) => conexao.usina).join(', ') : 'Nenhuma'
    }));

    const table = createDataTable<UcTableRow>({
      title: 'UCs cadastradas',
      eyebrow: 'Listagem',
      rows,
      emptyMessage: loadError ? 'Nao foi possivel carregar UCs.' : 'Nenhuma UC cadastrada ainda. Cadastre clientes com UC pela tela de Clientes ou use "Nova UC" aqui.',
      onRowClick: (row) => {
        selectedUc = ucs.find((item) => item.id === row.id) ?? null;
        isCreating = false;
        renderContent();
      },
      columns: [
        { key: 'cliente', label: 'Cliente' },
        { key: 'codigo', label: 'UC' },
        { key: 'usina', label: 'Usina' },
        { key: 'consumo', label: 'Consumo', align: 'right' },
        { key: 'tipoLigacao', label: 'Ligacao' }
      ]
    });
    const blocks: HTMLElement[] = [createDashboardCards(getUcMetrics(ucs)), pageActions];

    newUcButton.addEventListener('click', () => {
      if (clients.length === 0) {
        toast.error('Cadastre um cliente antes de criar uma UC avulsa.');
        return;
      }
      selectedUc = null;
      isCreating = true;
      renderContent();
    });

    pageActions.appendChild(newUcButton);

    if (isCreating || selectedUc) {
      blocks.push(createUcEditor());
    }

    blocks.push(table);
    content.replaceChildren(...blocks);
  }

  function createUcEditor(): HTMLElement {
    return createUcCard({
      uc: selectedUc ?? undefined,
      clients,
      availablePlants,
      onCancel: () => {
        selectedUc = null;
        isCreating = false;
        renderContent();
      },
      onSave: async (data) => {
        await saveUc(data);
        selectedUc = null;
        isCreating = false;
        await loadAll();
      },
      onDelete: selectedUc ? async () => {
        const confirmed = window.confirm(`Excluir a UC ${selectedUc?.codigo}? Essa acao nao pode ser desfeita.`);

        if (!confirmed || !selectedUc) return;

        loading.show();
        try {
          await deleteUc(selectedUc.id);
          toast.success('UC excluida.');
          selectedUc = null;
          await loadAll();
        } catch {
          toast.error('Nao foi possivel excluir a UC.');
        } finally {
          loading.hide();
        }
      } : undefined
    });
  }

  async function saveUc(data: UcPayload): Promise<void> {
    loading.show();
    try {
      if (selectedUc) {
        await updateUc(selectedUc.id, data);
        toast.success('UC atualizada.');
      } else {
        await createUc(data);
        toast.success('UC cadastrada.');
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Nao foi possivel salvar a UC.');
    } finally {
      loading.hide();
    }
  }
}
