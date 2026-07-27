// frontend/src/pages/UcsPage.ts
import { createDashboardCards } from '../components/DashboardCards';
import { createDataTable } from '../components/DataTable';
import { createUcCard, type UcFormData } from '../components/UcCard';
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
} from '../services/ucService';

type UcTableRow = {
  id: number;
  cliente: string;
  codigo: string;
  usina: string;
  consumo: string;
  status: string;
};

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
    title: 'Acompanhe unidades consumidoras, cliente vinculado e conexao com usinas'
  });

  loadUcs();

  return layout;

  async function loadUcs(): Promise<void> {
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

  function toTableRows(): UcTableRow[] {
    return ucs.map((uc) => ({
      id: uc.id,
      cliente: uc.clienteNome ?? '-',
      codigo: uc.apelido ? `${uc.codigo} (${uc.apelido})` : uc.codigo,
      usina: uc.conexoes.length > 0 ? uc.conexoes.map((conexao) => conexao.usina).join(', ') : '-',
      consumo: uc.consumo || '-',
      status: uc.conexoes.length > 0 ? 'Conectada' : 'Sem usina'
    }));
  }

  function renderContent(): void {
    const pageActions = createElement('div', { className: 'page-actions' });
    const newUcButton = createElement('button', { textContent: 'Nova UC', type: 'button' });
    const canCreate = clients.length > 0;
    const table = createDataTable<UcTableRow>({
      title: 'UCs cadastradas',
      eyebrow: 'Listagem',
      rows: toTableRows(),
      emptyMessage: loadError ? 'Nao foi possivel carregar UCs.' : 'Nenhuma UC cadastrada ainda.',
      onRowClick: (row) => {
        selectedUc = ucs.find((uc) => uc.id === row.id) ?? null;
        isCreating = false;
        renderContent();
      },
      columns: [
        { key: 'cliente', label: 'Cliente' },
        { key: 'codigo', label: 'UC' },
        { key: 'usina', label: 'Usina' },
        { key: 'consumo', label: 'Consumo', align: 'right' },
        { key: 'status', label: 'Status' }
      ]
    });
    const blocks: HTMLElement[] = [createDashboardCards(getUcMetrics(ucs)), pageActions];

    newUcButton.disabled = !canCreate;
    newUcButton.title = canCreate ? '' : 'Cadastre um cliente antes de criar uma UC.';
    newUcButton.addEventListener('click', () => {
      if (!canCreate) return;
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
        await loadUcs();
      },
      onDelete: selectedUc ? async () => {
        const confirmed = window.confirm(`Excluir a UC ${selectedUc?.codigo}? Essa acao nao pode ser desfeita.`);
        if (!confirmed || !selectedUc) return;

        loading.show();
        try {
          await deleteUc(selectedUc.id);
          toast.success('UC excluida.');
          selectedUc = null;
          await loadUcs();
        } catch {
          toast.error('Nao foi possivel excluir a UC.');
        } finally {
          loading.hide();
        }
      } : undefined
    });
  }

  async function saveUc(data: UcFormData): Promise<void> {
    loading.show();
    try {
      const payload: UcPayload = {
        clienteId: data.clienteId,
        codigo: data.codigo,
        apelido: data.apelido,
        consumo: data.consumo,
        baseTarifaria: data.baseTarifaria,
        desconto: data.desconto,
        tipoLigacao: data.tipoLigacao,
        conexoes: data.conexoes.map((conexao) => ({ plantId: conexao.plantId, percentual: conexao.percentual }))
      };

      if (selectedUc) {
        await updateUc(selectedUc.id, payload);
        toast.success('UC atualizada.');
      } else {
        await createUc(payload);
        toast.success('UC cadastrada.');
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Nao foi possivel salvar a UC.');
    } finally {
      loading.hide();
    }
  }
}