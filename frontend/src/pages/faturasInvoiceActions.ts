import { createExternalLink, currentBoleto, formatReference, isHttpsUrl } from '../components/FaturasUi';
import { createModalShell } from '../components/Modal';
import { createElement } from '../dom';
import { deleteBillingInvoice, downloadBillingInvoice, reprocessBillingInvoice, type BillingInvoice } from '../services/billingCalculationsService';
import { t } from '../services/i18nService';

type InvoiceActionsContext = {
  empresaId?: number;
  canIssue: boolean;
  toast: { success: (message: string) => void; error: (message: string) => void };
  load: () => Promise<void>;
  clientName: (invoice: BillingInvoice) => string;
};

export function createInvoiceActions(ctx: InvoiceActionsContext): {
  invoiceDownloadButton: (invoice: BillingInvoice) => HTMLButtonElement;
  invoiceActionsCell: (item: BillingInvoice) => HTMLElement;
} {
  const { empresaId, canIssue, toast, load, clientName } = ctx;
  const fail = (cause: unknown, fallback: string) => toast.error(cause instanceof Error && cause.message ? cause.message : fallback);
  const describe = (item: BillingInvoice) => `${clientName(item)} (${formatReference(item.competencia)})`;

  function rowButton(label: string, item: BillingInvoice, className: string, run: () => Promise<void> | void): HTMLButtonElement {
    const button = createElement('button', { className, type: 'button', textContent: label });
    button.setAttribute('aria-label', `${label} - ${describe(item)}`);
    button.addEventListener('click', (event) => {
      event.stopPropagation();
      button.disabled = true;
      void Promise.resolve(run()).finally(() => { button.disabled = false; });
    });
    button.addEventListener('keydown', (event) => event.stopPropagation());
    return button;
  }

  const invoiceDownloadButton = (invoice: BillingInvoice, label = t('faturas.page.downloadPdf')) =>
    rowButton(label, invoice, 'secondary-button', () => downloadBillingInvoice(invoice.id, empresaId).catch((cause) => fail(cause, t('faturas.page.downloadError'))));

  async function copyLink(url: string): Promise<void> {
    try {
      if (!isHttpsUrl(url)) throw new Error('invalid link');
      await navigator.clipboard.writeText(url);
      toast.success(t('faturas.page.linkCopied'));
    } catch {
      toast.error(`${t('faturas.page.linkCopyFailed')} ${url}`);
    }
  }

  async function reprocess(item: BillingInvoice): Promise<void> {
    try {
      const result = await reprocessBillingInvoice(item.id, empresaId);
      const problems = result.invoice.problemas;
      if (problems.length) toast.error(problems[0].message); else toast.success(t('faturas.page.reprocessSuccess'));
      await load();
    } catch (cause) {
      fail(cause, t('faturas.page.reprocessError'));
    }
  }

  function confirmDelete(item: BillingInvoice): void {
    const { overlay, body, close } = createModalShell(t('faturas.page.deleteModalTitle'), t('faturas.page.eyebrow'));
    const confirm = createElement('button', { className: 'danger-button', type: 'button', textContent: t('faturas.page.deleteAction') });
    const cancel = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('common.cancel') });
    cancel.addEventListener('click', close);
    confirm.addEventListener('click', () => {
      confirm.disabled = true;
      void deleteBillingInvoice(item.id, empresaId)
        .then(() => { close(); toast.success(t('faturas.page.invoiceDeletedSuccess')); return load(); })
        .catch((cause) => { close(); fail(cause, t('faturas.page.deleteInvoiceError')); });
    });
    const actions = createElement('div', { className: 'form-actions' });
    actions.append(confirm, cancel);
    body.append(createElement('strong', { textContent: describe(item) }), createElement('p', { textContent: t('faturas.page.confirmDeleteInvoice') }), actions);
    document.body.appendChild(overlay);
  }

  function invoiceActionsCell(item: BillingInvoice): HTMLElement {
    const cell = createElement('div', { className: 'faturas-row-actions' });
    const { boleto, canMutate } = currentBoleto(item.contextualCharges ?? []);
    if (item.documentoDisponivel) cell.appendChild(invoiceDownloadButton(item, t('faturas.page.actionPdf')));
    const open = createExternalLink(boleto?.boletoUrl, t('faturas.page.actionBoleto'));
    if (open) {
      open.setAttribute('aria-label', `${t('faturas.page.actionBoleto')} - ${describe(item)}`);
      open.addEventListener('click', (event) => event.stopPropagation());
      open.addEventListener('keydown', (event) => event.stopPropagation());
      cell.appendChild(open);
    }
    const link = boleto?.invoiceUrl ?? boleto?.boletoUrl;
    if (link) cell.appendChild(rowButton(t('faturas.page.actionLink'), item, 'secondary-button', () => copyLink(link)));
    if (canIssue && canMutate && item.problemas.length) cell.appendChild(rowButton(t('faturas.page.actionReprocess'), item, 'secondary-button', () => reprocess(item)));
    if (canIssue && canMutate) cell.appendChild(rowButton(t('faturas.page.deleteAction'), item, 'danger-button', () => confirmDelete(item)));
    return cell;
  }

  return { invoiceDownloadButton, invoiceActionsCell };
}
