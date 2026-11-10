import { createModalShell } from '../components/Modal';
import { createElement } from '../dom';
import { useToast } from '../hooks/useToast';
import { downloadBillingInvoice } from '../services/billingCalculationsService';
import type { FaturaRow } from '../services/faturasService';
import { t } from '../services/i18nService';

type PanelOptions = { invoiceId: number; empresaId?: number; onClose: () => void };

const isHttps = (url: string | null | undefined): url is string => Boolean(url?.startsWith('https://'));

export function openBoletoPanel(fatura: FaturaRow, { invoiceId, empresaId, onClose }: PanelOptions): void {
  const toast = useToast();
  const { overlay, body } = createModalShell(t('financeiro.panel.title'), t('financeiro.page.title'), onClose);
  const actions = createElement('div', { className: 'form-actions' });

  if (isHttps(fatura.boletoUrl)) {
    const open = createElement('a', { className: 'secondary-button', textContent: t('financeiro.panel.download') });
    open.href = fatura.boletoUrl; open.target = '_blank'; open.rel = 'noopener noreferrer';
    actions.appendChild(open);
  }

  const link = fatura.invoiceUrl ?? fatura.boletoUrl;
  const copy = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('financeiro.panel.copyLink') });
  copy.addEventListener('click', async () => {
    try {
      if (!isHttps(link)) throw new Error('invalid link');
      await navigator.clipboard.writeText(link);
      toast.success(t('financeiro.panel.copied'));
    } catch {
      toast.error(`${t('financeiro.panel.copyFailed')} ${link ?? ''}`.trim());
    }
  });
  actions.appendChild(copy);

  if (fatura.billingMode === 'unified') {
    const pdf = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('financeiro.panel.invoicePdf') });
    pdf.addEventListener('click', () => {
      pdf.disabled = true;
      void downloadBillingInvoice(invoiceId, empresaId)
        .catch((cause) => toast.error(cause instanceof Error && cause.message ? cause.message : t('financeiro.panel.invoiceError')))
        .finally(() => { pdf.disabled = false; });
    });
    actions.appendChild(pdf);
  }

  body.appendChild(actions);
  document.body.appendChild(overlay);
}
