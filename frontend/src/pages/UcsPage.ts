import { createDashboardCards } from '../components/DashboardCards';
import { createDataTable } from '../components/DataTable';
import { createInfoField } from '../components/ClientDetailView';
import { createIcon } from '../components/Icon';
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
  let selectedUcId: number | null = null;
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
    const selectedUc = ucs.find((item) => item.id === selectedUcId) ?? null;

    const pageActions = createElement('div', { className: 'page-actions' });
    const spacer = createElement('div');
    spacer.style.flex = '1 0 auto';
    spacer.style.minWidth = '0';
    const newUcButton = createElement('button', { className: 'button-with-icon', type: 'button' });
    newUcButton.append(createIcon('plus'), document.createTextNode('Nova UC'));

    newUcButton.addEventListener('click', () => {
      if (clients.length === 0) {
        toast.error('Cadastre um cliente antes de criar uma UC avulsa.');
        return;
      }
      openUcEditor(null);
    });

    pageActions.append(spacer, newUcButton);

    const rows: UcTableRow[] = ucs.map((uc) => ({
      ...uc,
      cliente: uc.clienteNome ?? '-',
      usina: uc.conexoes.length > 0 ? uc.conexoes.map((conexao) => conexao.usina).join(', ') : 'Nenhuma'
    }));

    const table = createDataTable<UcTableRow>({
      title: 'UCs cadastradas',
      eyebrow: 'Listagem',
      rows,
      emptyMessage: loadError
        ? 'Nao foi possivel carregar UCs.'
        : 'Nenhuma UC cadastrada ainda. Cadastre clientes com UC pela tela de Clientes ou use "Nova UC" aqui.',
      onRowClick: (row) => {
        selectedUcId = row.id;
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

    const blocks = [createDashboardCards(getUcMetrics(ucs)), pageActions, table];

    if (!selectedUc) {
      content.replaceChildren(...blocks);
      return;
    }

    // Mesmo padrao de PendenciasPage.ts: coluna da esquerda com seu proprio
    // content-stack, painel de detalhe fixo (sticky) a direita.
    const listColumn = createElement('div', { className: 'content-stack' });
    listColumn.append(...blocks);

    const wrapper = createElement('div', { className: 'list-detail-grid' });
    wrapper.append(listColumn, createUcDetailPanel(selectedUc));
    content.replaceChildren(wrapper);
  }

  // So-leitura -- reaproveita createInfoField (mesmo helper que
  // ClientDetailView.ts e PlantsPage.ts ja usam pro par label/valor), sem
  // secao de "Observacoes" a pedido. Acoes (Editar/Excluir) abrem o mesmo
  // UcCard.ts de sempre -- nenhuma mudanca nele.
  function createUcDetailPanel(uc: UcRow): HTMLElement {
    const panel = createElement('aside', { className: 'detail-info-panel sticky' });

    const title = createElement('div', { className: 'panel-title' });
    const titleText = createElement('div');
    const eyebrow = createElement('span', { className: 'eyebrow', textContent: 'UC' });
    const heading = createElement('h2', { textContent: uc.codigo || 'UC' });
    const closeButton = createElement('button', { className: 'icon-button neutral', type: 'button' });
    closeButton.appendChild(createIcon('x'));
    closeButton.title = 'Fechar';
    closeButton.addEventListener('click', () => {
      selectedUcId = null;
      renderContent();
    });

    titleText.append(eyebrow, heading);
    title.append(titleText, closeButton);

    const grid = createElement('div', { className: 'detail-info-grid' });
    grid.append(
      createInfoField('Cliente', uc.clienteNome ?? '-'),
      createInfoField('Código ANEEL', uc.codigoAneel || 'Não informado'),
      createInfoField('Apelido', uc.apelido || 'Não informado'),
      createInfoField('CPF/CNPJ da UC', uc.documento || 'Não informado'),
      createInfoField('Endereço', uc.endereco || 'Não informado'),
      createInfoField('CEP', uc.cep || 'Não informado'),
      createInfoField('Concessionária', uc.concessionaria || 'Não informado'),
      createInfoField('Consumo', uc.consumo || '-'),
      createInfoField('Base tarifária', uc.baseTarifaria),
      createInfoField('Desconto', uc.desconto || '-'),
      createInfoField('Ligação', uc.tipoLigacao),
      createInfoField('Geração própria', uc.geracaoPropria ? 'Sim' : 'Não'),
      createInfoField('Dia de emissão da fatura', uc.diaEmissaoFatura != null ? String(uc.diaEmissaoFatura) : 'Não informado'),
      createInfoField('Início do contrato', formatUcDate(uc.inicioContrato)),
      createInfoField('Término do contrato', formatUcDate(uc.terminoContrato)),
      createInfoField('Carência (meses)', uc.carenciaMeses != null ? String(uc.carenciaMeses) : 'Não informado'),
      createInfoField('Desconto na carência', uc.percentualDescontoCarencia || 'Não informado'),
      createInfoField(
        'Usinas conectadas',
        uc.conexoes.length > 0 ? uc.conexoes.map((conexao) => `${conexao.usina} (${conexao.percentual}%)`).join(', ') : 'Nenhuma'
      )
    );

    const actions = createElement('div', { className: 'form-actions' });
    const editButton = createElement('button', { className: 'secondary-button button-with-icon', type: 'button' });
    editButton.append(createIcon('edit'), document.createTextNode('Editar'));
    editButton.addEventListener('click', () => openUcEditor(uc));

    const deleteButton = createElement('button', { className: 'danger-button button-with-icon', type: 'button' });
    deleteButton.append(createIcon('trash'), document.createTextNode('Excluir'));
    deleteButton.addEventListener('click', () => confirmDeleteUc(uc));

    actions.append(editButton, deleteButton);

    panel.append(title, grid, actions);
    return panel;
  }

  // Abre o UcCard.ts de sempre, como modal solto no body -- mesmo padrao ja
  // usado em PlantsPage.ts (openPlantEditor). Nenhuma mudanca no UcCard.ts.
  function openUcEditor(uc: UcRow | null): void {
    document.body.appendChild(createUcCard({
      uc: uc ?? undefined,
      clients,
      availablePlants,
      onCancel: () => {
        document.querySelector('.modal-overlay')?.remove();
      },
      onSave: async (data) => {
        await saveUc(uc, data);
        document.querySelector('.modal-overlay')?.remove();
        await loadAll();
      },
      onDelete: uc ? () => {
        document.querySelector('.modal-overlay')?.remove();
        confirmDeleteUc(uc);
      } : undefined
    }));
  }

  async function saveUc(existing: UcRow | null, data: UcPayload): Promise<void> {
    loading.show();
    try {
      if (existing) {
        await updateUc(existing.id, data);
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

  async function confirmDeleteUc(uc: UcRow): Promise<void> {
    const confirmed = window.confirm(`Excluir a UC ${uc.codigo}? Essa acao nao pode ser desfeita.`);
    if (!confirmed) return;

    loading.show();
    try {
      await deleteUc(uc.id);
      toast.success('UC excluida.');
      if (selectedUcId === uc.id) selectedUcId = null;
      await loadAll();
    } catch {
      toast.error('Nao foi possivel excluir a UC.');
    } finally {
      loading.hide();
    }
  }
}

// Split-based, sem Date() -- mesmo motivo documentado em ClientDetailView.ts
// (evita o bug de "um dia antes" por causa de fuso horario).
function formatUcDate(value: string | null): string {
  if (!value) return 'Não informado';
  const [year, month, day] = value.split('-');
  return `${day}/${month}/${year}`;
}