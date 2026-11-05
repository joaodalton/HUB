import { createModal, selectField, textField, option, currentMonth } from '../components/FaturasUi';
import { createElement } from '../dom';
import { createFatura } from '../services/faturasService';
import type { BillingInvoice } from '../services/billingCalculationsService';
import type { ClientRow } from '../services/clientsService';
import type { UcRow } from '../services/ucsService';
import { t } from '../services/i18nService';

interface CreateModalOptions {
  invoice: BillingInvoice;
  clients: ClientRow[];
  ucs: UcRow[];
  canIssueInvoice: (invoice: BillingInvoice | null) => boolean;
  toast: { success: (message: string) => void; error: (message: string) => void };
  reload: () => Promise<void>;
}

export function openCreateModal({ invoice, clients, ucs, canIssueInvoice, toast, reload }: CreateModalOptions): void {
  const overlay = createModal(t('faturas.page.modalTitle'), t('faturas.page.eyebrow'));
  const form = createElement('form', { className: 'client-form' });
  const client = selectField(t('faturas.page.fieldCliente'), clients.map((item) => ({ value: String(item.id), label: item.nome })), true);
  const uc = selectField(t('faturas.page.fieldUc'), [], true);
  const concessionaria = textField(t('faturas.page.fieldConcessionaria'), 'text', '', true);
  concessionaria.input.readOnly = true;
  const competencia = textField(t('faturas.page.fieldCompetencia'), 'month', currentMonth(), true);
  const vencimento = textField(t('faturas.page.fieldVencimentoCobranca'), 'date', '', true);
  const valor = textField(t('faturas.page.fieldValorComercial'), 'number', '', true);
  valor.input.min = '0.01'; valor.input.step = '0.01';
  const notice = createElement('p', { className: 'fatura-notice', textContent: t('faturas.page.modalNotice') });
  const actions = createElement('div', { className: 'form-actions' });
  const submit = createElement('button', { type: 'submit', textContent: t('faturas.page.modalTitle') });
  const cancel = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('common.cancel') });
  cancel.addEventListener('click', () => overlay.remove());
  actions.append(submit, cancel);
  function refreshUcs(): void {
    const selectedClientId = Number(client.select.value);
    const options = ucs.filter((item) => item.clienteId === selectedClientId);
    uc.select.replaceChildren(...options.map((item) => option(String(item.id), item.codigo)));
    concessionaria.input.value = options[0]?.concessionaria ?? '';
  }
  client.select.addEventListener('change', refreshUcs);
  uc.select.addEventListener('change', () => { concessionaria.input.value = ucs.find((item) => item.id === Number(uc.select.value))?.concessionaria ?? ''; });
  refreshUcs();
  client.select.value = String(invoice.clientId);
  refreshUcs();
  uc.select.value = String(invoice.consumerUnitId);
  concessionaria.input.value = ucs.find((item) => item.id === invoice.consumerUnitId)?.concessionaria ?? '';
  competencia.input.value = invoice.competencia ?? '';
  client.select.disabled = true;
  uc.select.disabled = true;
  competencia.input.readOnly = true;
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!form.reportValidity() || !canIssueInvoice(invoice)) return;
    submit.disabled = true;
    try {
      await createFatura({ clienteId: Number(client.select.value), ucId: Number(uc.select.value), valor: Number(valor.input.value), competencia: competencia.input.value, mesVencimento: vencimento.input.value });
      toast.success(t('faturas.page.chargeSuccess')); overlay.remove(); await reload();
    } catch (cause) { toast.error(cause instanceof Error ? cause.message : t('faturas.page.chargeError')); }
    finally { submit.disabled = false; }
  });
  const grid = createElement('div', { className: 'form-grid' });
  client.field.classList.add('form-field-wide');
  grid.append(client.field, uc.field, concessionaria.field, competencia.field, vencimento.field, valor.field);
  form.append(grid, notice, actions);
  overlay.querySelector('.modal-body')?.appendChild(form);
}
