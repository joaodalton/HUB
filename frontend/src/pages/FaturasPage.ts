// frontend/src/pages/FaturasPage.ts
import { createDataTable } from '../components/DataTable';
import { createElement } from '../dom';
import { useGlobalLoading } from '../hooks/useGlobalLoading';
import { useToast } from '../hooks/useToast';
import { createBaseLayout } from '../layouts/BaseLayout';
import { getClients, type ClientRow } from '../services/clientsService';
import { getUcs, type UcRow } from '../services/ucsService';
import {
  cancelarFatura,
  createFatura,
  getFaturas,
  statusLabel,
  statusTone,
  type FaturaPayload,
  type FaturaRow
} from '../services/faturasService';

export function createFaturasPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const toast = useToast();
  const loading = useGlobalLoading();

  let faturas: FaturaRow[] = [];
  let clients: ClientRow[] = [];
  let ucs: UcRow[] = [];
  let loadError = false;

  const layout = createBaseLayout({
    content,
    eyebrow: 'Financeiro',
    title: 'Faturas geradas via ASAAS'
  });

  loadAll();

  return layout;

  async function loadAll(): Promise<void> {
    loading.show();
    try {
      [faturas, clients, ucs] = await Promise.all([getFaturas(), getClients(), getUcs()]);
      loadError = false;
    } catch {
      loadError = true;
      toast.error('Não foi possível carregar faturas. Verifique se o backend está rodando.');
    } finally {
      loading.hide();
      renderContent();
    }
  }

  function renderContent(): void {
    const pageActions = createElement('div', { className: 'page-actions' });
    const spacer = createElement('div');
    spacer.style.flex = '1 0 auto';
    const newButton = createElement('button', { textContent: 'Nova fatura', type: 'button' });
    newButton.addEventListener('click', () => openFaturaModal());
    pageActions.append(spacer, newButton);

    const table = createDataTable<FaturaRow>({
      title: 'Faturas',
      eyebrow: 'Listagem',
      rows: faturas,
      emptyMessage: loadError ? 'Não foi possível carregar faturas.' : 'Nenhuma fatura gerada ainda.',
      columns: [
        { key: 'clienteNome', label: 'Cliente' },
        { key: 'ucCodigo', label: 'UC', render: (f) => f.ucCodigo || '-' },
        { key: 'competencia', label: 'Competência' },
        { key: 'valorCobrado', label: 'Valor', align: 'right', render: (f) => formatCurrency(f.valorCobrado) },
        { key: 'vencimento', label: 'Vencimento', render: (f) => formatDate(f.vencimento) },
        {
          key: 'status',
          label: 'Status',
          render: (f) => {
            const tone = statusTone(f.status);
            return createElement('span', {
              className: tone === 'neutral' ? 'status-badge' : `status-badge tone-${tone}`,
              textContent: statusLabel(f.status)
            });
          }
        },
        {
          key: 'acoes',
          label: '',
          align: 'right',
          render: (f) => createRowActions(f)
        }
      ]
    });

    content.replaceChildren(pageActions, table);
  }

  function createRowActions(fatura: FaturaRow): HTMLElement {
    const wrap = createElement('div', { className: 'table-actions' });

    if (fatura.linkPagamento) {
      const linkButton = createElement('a', { className: 'small-button', textContent: 'Ver boleto' });
      linkButton.href = fatura.linkPagamento;
      linkButton.target = '_blank';
      linkButton.rel = 'noopener noreferrer';
      wrap.appendChild(linkButton);
    }

    if (fatura.status === 'pendente' || fatura.status === 'vencido') {
      const cancelButton = createElement('button', { className: 'danger-button', textContent: 'Cancelar', type: 'button' });
      cancelButton.addEventListener('click', () => handleCancelar(fatura));
      wrap.appendChild(cancelButton);
    }

    return wrap;
  }

  async function handleCancelar(fatura: FaturaRow): Promise<void> {
    if (!window.confirm(`Cancelar a fatura de ${fatura.clienteNome} (${fatura.competencia})?`)) return;

    loading.show();
    try {
      await cancelarFatura(fatura.id);
      toast.success('Fatura cancelada.');
      await loadAll();
    } catch {
      toast.error('Não foi possível cancelar a fatura.');
    } finally {
      loading.hide();
    }
  }

  function openFaturaModal(): void {
    const overlay = createElement('section', { className: 'modal-overlay' });
    const panel = createElement('article', { className: 'plant-card' });
    const form = createElement('form', { className: 'client-form' });

    const header = createElement('div', { className: 'form-header' });
    header.append(
      createElement('h2', { textContent: 'Nova fatura' }),
      Object.assign(createElement('button', { className: 'secondary-button', textContent: 'Fechar', type: 'button' }), {
        onclick: () => overlay.remove()
      })
    );

    const fields = createElement('div', { className: 'form-grid' });

    // Cliente
    const clienteField = createElement('label', { className: 'form-field' });
    const clienteSelect = createElement('select');
    const placeholderCliente = createElement('option', { textContent: 'Selecione um cliente' });
    placeholderCliente.value = '';
    clienteSelect.appendChild(placeholderCliente);
    const clienteMap = new Map(clients.map(c => [c.id, c]));
    clienteMap.forEach((client) => {
      const option = createElement('option', { textContent: client.nome });
      option.value = String(client.id);
      clienteSelect.appendChild(option);
    });
    clienteSelect.required = true;
    clienteField.append(createElement('span', { textContent: 'Cliente' }), clienteSelect);

    // UC (apenas UCs do cliente selecionado)
    const ucField = createElement('label', { className: 'form-field' });
    const ucSelect = createElement('select');
    const placeholderUc = createElement('option', { textContent: 'Selecione a UC' });
    placeholderUc.value = '';
    ucSelect.appendChild(placeholderUc);
    ucSelect.required = true;
    const availableUcs = createElement('span', { className: 'form-field-hint', textContent: 'Selecione o cliente primeiro' });
    fields.append(clienteField, ucField);
    ucField.append(availableUcs, ucSelect);

    // Competência
    const competenciaField = createElement('label', { className: 'form-field' });
    const competenciaInput = createElement('input');
    competenciaInput.type = 'month';
    competenciaInput.required = true;
    competenciaField.append(createElement('span', { textContent: 'Competência' }), competenciaInput);

    // Valor
    const valorField = createElement('label', { className: 'form-field' });
    const valorInput = createElement('input');
    valorInput.type = 'number';
    valorInput.min = '0.01';
    valorInput.step = '0.01';
    valorInput.required = true;
    valorField.append(createElement('span', { textContent: 'Valor cobrado (R$)' }), valorInput);

    // Vencimento
    const vencimentoField = createElement('label', { className: 'form-field' });
    const vencimentoInput = createElement('input');
    vencimentoInput.type = 'date';
    vencimentoInput.required = true;
    vencimentoField.append(createElement('span', { textContent: 'Vencimento' }), vencimentoInput);

    fields.append(competenciaField, valorField, vencimentoField);

    const actions = createElement('div', { className: 'form-actions' });
    const saveButton = createElement('button', { textContent: 'Gerar cobrança', type: 'submit' });
    actions.appendChild(saveButton);

    overlay.addEventListener('click', (event) => {
      if (event.target === overlay) overlay.remove();
    });

    clienteSelect.addEventListener('change', () => {
      const selectedClientId = Number(clienteSelect.value);
      ucSelect.replaceChildren();

      if (!selectedClientId || !clienteMap.has(selectedClientId)) {
        availableUcs.textContent = 'Selecione o cliente primeiro';
        ucSelect.appendChild(placeholderUc);
        ucSelect.disabled = true;
        return;
      }

      availableUcs.textContent = 'Selecione a UC deste cliente';
      ucSelect.disabled = false;
      const clienteUcs = ucs.filter(uc => uc.clienteId === selectedClientId);
      if (clienteUcs.length === 0) {
        availableUcs.textContent = 'Este cliente não tem UC cadastrada';
        ucSelect.appendChild(placeholderUc);
        ucSelect.disabled = true;
        return;
      }

      clienteUcs.forEach((uc) => {
        const option = createElement('option', { textContent: `${uc.codigo} — ${uc.consumo ? `R$ ${uc.consumo.toFixed(2)}` : 'Sem consumo'}` });
        option.value = String(uc.id);
        ucSelect.appendChild(option);
      });
    });

    form.addEventListener('submit', async (event) => {
      event.preventDefault();

      if (!clienteSelect.value) {
        clienteSelect.reportValidity();
        return;
      }

      const selectedClientId = Number(clienteSelect.value);
      const selectedUcId = ucSelect.value ? Number(ucSelect.value) : null;

      const payload: FaturaPayload = {
        clienteId: selectedClientId,
        ucId: selectedUcId,
        competencia: competenciaInput.value,
        valorCobrado: Number(valorInput.value),
        vencimento: vencimentoInput.value
      };

      saveButton.disabled = true;
      saveButton.textContent = 'Gerando...';

      try {
        await createFatura(payload);
        toast.success('Fatura criada e cobrança gerada no ASAAS.');
        overlay.remove();
        await loadAll();
      } catch (error) {
        toast.error(error instanceof Error ? error.message : 'Não foi possível criar a fatura.');
        saveButton.disabled = false;
        saveButton.textContent = 'Gerar cobrança';
      }
    });

    form.append(header, fields, actions);
    panel.append(form);
    overlay.appendChild(panel);
    document.body.appendChild(overlay);
  }
}

function formatCurrency(value: number): string {
  return value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

function formatDate(value: string): string {
  if (!value) return '-';
  const [year, month, day] = value.split('-');
  return `${day}/${month}/${year}`;
}
