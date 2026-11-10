import { createIcon } from './Icon';
import { createModalShell } from './Modal';
import { createElement } from '../dom';
import { useToast } from '../hooks/useToast';
import { ApiRequestError } from '../services/apiClient';
import { getCurrentUser } from '../services/authService';
import { uploadBillingInvoice, uploadTenantBillingInvoice } from '../services/billingCalculationsService';
import { t } from '../services/i18nService';

export const INVOICES_IMPORTED_EVENT = 'hub:invoices-imported';
export type InvoicesImportedDetail = { imported: number; duplicates: number; failed: number };

type FileResult = { name: string; kind: 'imported' | 'duplicate' | 'failed'; text: string };

function navigate(path: string): void {
  window.history.pushState({}, '', path);
  window.dispatchEvent(new PopStateEvent('popstate'));
}

export function createInvoiceImportButton(): HTMLElement | null {
  const user = getCurrentUser();
  const empresaId = user?.isPlatformAdmin ? user.platformViewEmpresaId : null;
  if (!user || (user.isPlatformAdmin ? !empresaId : !['owner', 'admin', 'financial'].includes(user.role ?? ''))) return null;
  const toast = useToast();
  const wrap = createElement('span', { className: 'faturas-upload-action' });
  const button = createElement('button', { className: 'secondary-button button-with-icon', type: 'button' });
  button.append(createIcon('upload'), document.createTextNode(t('faturas.import.button')));
  const input = createElement('input');
  input.type = 'file';
  input.multiple = true;
  input.accept = '.pdf,application/pdf';
  input.hidden = true;
  input.setAttribute('aria-label', t('faturas.import.fileAriaLabel'));
  button.addEventListener('click', () => input.click());
  input.addEventListener('change', async () => {
    const files = Array.from(input.files ?? []);
    if (!files.length) return;
    button.disabled = true;
    try {
      finish(await sendAll(files));
    } finally {
      button.disabled = false;
      input.value = '';
    }
  });
  wrap.append(button, input);
  return wrap;

  async function sendAll(files: File[]): Promise<FileResult[]> {
    const results: FileResult[] = [];
    let limited = false;
    for (const file of files) {
      if (limited) { results.push({ name: file.name, kind: 'failed', text: t('faturas.import.notSentRateLimit') }); continue; }
      try {
        const sent = empresaId ? await uploadBillingInvoice(empresaId, file) : await uploadTenantBillingInvoice(file);
        results.push(sent.duplicate
          ? { name: file.name, kind: 'duplicate', text: t('faturas.import.rowDuplicate') }
          : { name: file.name, kind: 'imported', text: t('faturas.import.rowImported') });
      } catch (error) {
        limited = error instanceof ApiRequestError && error.status === 429;
        results.push({
          name: file.name, kind: 'failed',
          text: limited ? t('faturas.import.notSentRateLimit')
            : error instanceof Error && error.message ? error.message : t('faturas.import.unknownError')
        });
      }
    }
    return results;
  }

  function finish(results: FileResult[]): void {
    const count = (kind: FileResult['kind']) => results.filter((item) => item.kind === kind).length;
    const detail: InvoicesImportedDetail = { imported: count('imported'), duplicates: count('duplicate'), failed: count('failed') };
    const outside = window.location.pathname !== '/faturas';
    const goToFaturas = { label: t('faturas.import.viewInFaturas'), onClick: () => navigate('/faturas') };
    if (detail.imported || detail.duplicates) {
      const parts = [
        detail.imported ? t('faturas.import.toastImported').replace('{n}', String(detail.imported)) : '',
        detail.duplicates ? t('faturas.import.toastDuplicates').replace('{n}', String(detail.duplicates)) : ''
      ].filter(Boolean);
      toast.success(parts.join(' '), outside ? goToFaturas : undefined);
      window.dispatchEvent(new CustomEvent<InvoicesImportedDetail>(INVOICES_IMPORTED_EVENT, { detail }));
    }
    if (detail.failed && !detail.imported && !detail.duplicates) toast.error(t('faturas.import.toastAllFailed').replace('{n}', String(detail.failed)));
    if (detail.failed) openResultModal(results, outside ? goToFaturas : null);
  }
}

function openResultModal(results: FileResult[], action: { label: string; onClick: () => void } | null): void {
  const modal = createModalShell(t('faturas.import.resultTitle'));
  const list = createElement('ul', { className: 'faturas-import-results' });
  results.forEach((item) => {
    const prefix = item.kind === 'failed' ? `${t('faturas.import.errorPrefix')}: ` : '';
    list.appendChild(createElement('li', { textContent: `${item.name} - ${prefix}${item.text}` }));
  });
  modal.body.appendChild(list);
  if (action) {
    const link = createElement('button', { className: 'secondary-button', type: 'button', textContent: action.label });
    link.addEventListener('click', () => { modal.close(); action.onClick(); });
    modal.body.appendChild(link);
  }
  document.body.appendChild(modal.overlay);
}
