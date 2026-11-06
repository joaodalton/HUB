import { createDataTable } from './DataTable';
import { createIcon } from './Icon';
import { createElement } from '../dom';
import { useToast } from '../hooks/useToast';
import { getCurrentUser } from '../services/authService';
import {
  getBillingInvoices, getTenantBillingInvoices, uploadBillingInvoice,
  uploadTenantBillingInvoice, type BillingInvoice
} from '../services/billingCalculationsService';
import type { ClientRow } from '../services/clientsService';
import { extracaoLabel, validacaoLabel } from './FaturasUi';
import { t } from '../services/i18nService';

export function createConcessionariaInvoicesPanel(clients: ClientRow[]): HTMLElement {
  const panel = createElement('section', { className: 'content-stack' });
  const user = getCurrentUser();
  const platformEmpresaId = user?.isPlatformAdmin ? user.platformViewEmpresaId : null;
  let invoices: BillingInvoice[] = [];
  let error = false;
  void load();
  return panel;

  async function load(): Promise<void> {
    if (user?.isPlatformAdmin && !platformEmpresaId) {
      error = true;
      render();
      return;
    }
    try {
      invoices = user?.isPlatformAdmin && platformEmpresaId
        ? await getBillingInvoices(platformEmpresaId) : await getTenantBillingInvoices();
      error = false;
    } catch {
      error = true;
    }
    render();
  }

  function render(): void {
    const intro = createElement('div', { className: 'faturas-toolbar' });
    const copy = createElement('div', { className: 'faturas-toolbar-copy' });
    copy.append(createElement('h2', { textContent: t('faturas.concessionariaPanel.title') }),
      createElement('p', { textContent: t('faturas.concessionariaPanel.description') }));
    intro.appendChild(copy);
    const table = createDataTable<BillingInvoice>({
      title: t('faturas.concessionariaPanel.tableTitle'), eyebrow: `${invoices.length} ${t('faturas.concessionariaPanel.recordsParens')}`, rows: invoices,
      emptyMessage: user?.isPlatformAdmin && !platformEmpresaId ? t('faturas.concessionariaPanel.selectCompany')
        : error ? t('faturas.concessionariaPanel.loadError') : t('faturas.concessionariaPanel.empty'),
      columns: [
        { key: 'id', label: t('faturas.concessionariaPanel.colId'), render: (item) => String(item.id) },
        { key: 'client', label: t('faturas.concessionariaPanel.colCliente'), render: (item) => clients.find((client) => client.id === item.clientId)?.nome ?? t('faturas.concessionariaPanel.clientUnavailable') },
        { key: 'competencia', label: t('faturas.concessionariaPanel.colCompetencia'), render: (item) => item.competencia ?? t('faturas.concessionariaPanel.pending') },
        { key: 'extraction', label: t('faturas.concessionariaPanel.colExtracao'), render: (item) => extracaoLabel(item.statusExtracao) },
        { key: 'validation', label: t('faturas.concessionariaPanel.colValidacao'), render: (item) => validacaoLabel(item.statusValidacao) }
      ]
    });
    panel.replaceChildren(intro, table);
  }
}

export function createConcessionariaUploadButton(onUploaded: () => void): HTMLElement | null {
  const user = getCurrentUser();
  const empresaId = user?.isPlatformAdmin ? user.platformViewEmpresaId : null;
  if (user?.isPlatformAdmin ? !empresaId : !['owner', 'admin', 'financial'].includes(user?.role ?? '')) return null;
  const toast = useToast();
  const wrap = createElement('span', { className: 'faturas-upload-action' });
  const button = createElement('button', { className: 'secondary-button button-with-icon', type: 'button' });
  button.append(createIcon('upload'), document.createTextNode(t('faturas.concessionariaPanel.uploadPdf')));
  const input = createElement('input');
  input.type = 'file';
  input.accept = '.pdf,application/pdf';
  input.hidden = true;
  input.setAttribute('aria-label', t('faturas.concessionariaPanel.fileAriaLabel'));
  button.addEventListener('click', () => input.click());
  input.addEventListener('change', async () => {
    const file = input.files?.[0];
    if (!file) return;
    button.disabled = true;
    try {
      const result = empresaId ? await uploadBillingInvoice(empresaId, file) : await uploadTenantBillingInvoice(file);
      toast.success(result.duplicate ? t('faturas.concessionariaPanel.alreadyReceived') : t('faturas.concessionariaPanel.received'));
      onUploaded();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('faturas.concessionariaPanel.uploadError'));
    } finally {
      button.disabled = false;
      input.value = '';
    }
  });
  wrap.append(button, input);
  return wrap;
}
