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
    copy.append(createElement('h2', { textContent: 'Faturas da concessionária (PDF)' }),
      createElement('p', { textContent: 'Envie o documento original para processamento. Este upload não emite cobrança ASAAS.' }));
    intro.appendChild(copy);
    const table = createDataTable<BillingInvoice>({
      title: 'Documentos recebidos', eyebrow: `${invoices.length} registro(s)`, rows: invoices,
      emptyMessage: user?.isPlatformAdmin && !platformEmpresaId ? 'Selecione uma empresa na plataforma.'
        : error ? 'Não foi possível carregar os documentos.' : 'Nenhum PDF recebido.',
      columns: [
        { key: 'id', label: 'ID', render: (item) => String(item.id) },
        { key: 'client', label: 'Cliente', render: (item) => clients.find((client) => client.id === item.clientId)?.nome ?? 'Cliente indisponível' },
        { key: 'competencia', label: 'Competência', render: (item) => item.competencia ?? 'Pendente' },
        { key: 'extraction', label: 'Extração', render: (item) => item.statusExtracao },
        { key: 'validation', label: 'Validação', render: (item) => item.statusValidacao }
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
  button.append(createIcon('upload'), document.createTextNode('Enviar PDF'));
  const input = createElement('input');
  input.type = 'file';
  input.accept = '.pdf,application/pdf';
  input.hidden = true;
  input.setAttribute('aria-label', 'Arquivo PDF da concessionária');
  button.addEventListener('click', () => input.click());
  input.addEventListener('change', async () => {
    const file = input.files?.[0];
    if (!file) return;
    button.disabled = true;
    try {
      const result = empresaId ? await uploadBillingInvoice(empresaId, file) : await uploadTenantBillingInvoice(file);
      toast.success(result.duplicate ? 'Fatura já recebida.' : 'Fatura recebida.');
      onUploaded();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Não foi possível enviar o PDF.');
    } finally {
      button.disabled = false;
      input.value = '';
    }
  });
  wrap.append(button, input);
  return wrap;
}
