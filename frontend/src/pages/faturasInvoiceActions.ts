import { createElement } from '../dom';
import { ApiRequestError } from '../services/apiClient';
import { deleteBillingInvoice, downloadBillingInvoice, type BillingInvoice } from '../services/billingCalculationsService';
import { cancelFatura, type FaturaRow } from '../services/faturasService';
import { t } from '../services/i18nService';

type InvoiceActionsContext = {
  empresaId?: number;
  toast: { success: (message: string) => void; error: (message: string) => void };
  load: () => Promise<void>;
  contextualCharges: (invoice: BillingInvoice) => FaturaRow[];
};

export function createInvoiceActions(ctx: InvoiceActionsContext): {
  invoiceDownloadButton: (invoice: BillingInvoice) => HTMLButtonElement;
  invoicePdfCell: (item: BillingInvoice) => HTMLElement | string;
} {
  const { empresaId, toast, load, contextualCharges } = ctx;

  function invoiceDownloadButton(invoice: BillingInvoice): HTMLButtonElement {
    const button = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('faturas.page.downloadPdf') });
    button.style.width = 'fit-content';
    button.addEventListener('click', (event) => {
      event.stopPropagation();
      button.disabled = true;
      void downloadBillingInvoice(invoice.id, empresaId).catch((cause) => {
        toast.error(cause instanceof Error ? cause.message : t('faturas.page.downloadError'));
      }).finally(() => { button.disabled = false; });
    });
    button.addEventListener('keydown', (event) => event.stopPropagation());
    return button;
  }

  function deleteBoletoButton(charge: FaturaRow): HTMLButtonElement {
    const button = createElement('button', { className: 'danger-button', type: 'button', textContent: t('faturas.detail.deleteBoleto') });
    button.addEventListener('click', (event) => {
      event.stopPropagation();
      if (!window.confirm(t('faturas.detail.confirmCancelCharge'))) return;
      button.disabled = true;
      void cancelFatura(charge.id)
        .then(() => { toast.success(t('faturas.detail.chargeCanceled')); return load(); })
        .catch((cause) => { toast.error(cause instanceof Error ? cause.message : t('faturas.detail.actionError')); })
        .finally(() => { button.disabled = false; });
    });
    button.addEventListener('keydown', (event) => event.stopPropagation());
    return button;
  }

  function deleteInvoiceButton(item: BillingInvoice): HTMLButtonElement {
    const button = createElement('button', { className: 'danger-button', type: 'button', textContent: t('faturas.page.deleteInvoice') });
    button.style.width = 'fit-content';
    button.addEventListener('click', (event) => {
      event.stopPropagation();
      if (!window.confirm(t('faturas.page.confirmDeleteInvoice'))) return;
      button.disabled = true;
      void deleteBillingInvoice(item.id, empresaId)
        .then(() => { toast.success(t('faturas.page.invoiceDeletedSuccess')); return load(); })
        .catch((cause) => {
          if (cause instanceof ApiRequestError && cause.code === 'INVOICE_HAS_BOLETO') {
            toast.error(t('faturas.page.deleteInvoiceHasBoleto'));
          } else {
            toast.error(cause instanceof Error ? cause.message : t('faturas.page.deleteInvoiceError'));
          }
        })
        .finally(() => { button.disabled = false; });
    });
    button.addEventListener('keydown', (event) => event.stopPropagation());
    return button;
  }

  function invoicePdfCell(item: BillingInvoice): HTMLElement | string {
    const cancelableCharge = contextualCharges(item).find((charge) => charge.asaasId && charge.asaasStatus === 'pending');
    if (!item.documentoDisponivel && !cancelableCharge) return '—';
    const cell = createElement('div', { className: 'form-actions' });
    cell.style.justifyContent = 'center';
    if (item.documentoDisponivel) {
      cell.appendChild(invoiceDownloadButton(item));
      cell.appendChild(deleteInvoiceButton(item));
    }
    if (cancelableCharge) cell.appendChild(deleteBoletoButton(cancelableCharge));
    return cell;
  }

  return { invoiceDownloadButton, invoicePdfCell };
}
