import { createElement } from '../dom';
import { createIcon } from './Icon';
import { useToast } from '../hooks/useToast';
import { t } from '../services/i18nService';
import {
  deleteDocument,
  downloadDocumentFile,
  getDocuments,
  renameDocument,
  uploadDocument,
  type DocumentRow
} from '../services/documentsService';

// Categoria de documento saiu da interface (decisao 2026-07-30) -- atrapalhava mais
// do que ajudava no fluxo. O campo continua existindo no banco (agora opcional),
// so nao aparece mais aqui nem em nenhum outro lugar de upload.
// plantId: mesmo painel reaproveitado pra documentos de usina (Task 11) --
// so troca o parametro de filtro/upload (clienteId -> plantId).
export function createClientDocumentsPanel(clientId: number | undefined, plantId?: number): HTMLElement {
  const toast = useToast();
  const panel = createElement('div', { className: 'client-documents-panel' });
  const title = createElement('span', { className: 'plant-connection-title', textContent: t('clients.documents.title') });
  const entityLabel = plantId ? t('clients.documents.entityPlant') : t('clients.documents.entityClient');

  panel.appendChild(title);

  if (!clientId && !plantId) {
    panel.appendChild(createElement('p', {
      className: 'empty-state small',
      textContent: `${t('clients.documents.savePrefix')} ${entityLabel} ${t('clients.documents.saveSuffix')}`
    }));
    return panel;
  }

  const list = createElement('div', { className: 'document-list' });
  const fileInput = createElement('input');
  const dropButton = createElement('button', { className: 'upload-dropzone', type: 'button' });

  dropButton.appendChild(createIcon('upload'));
  dropButton.setAttribute('aria-label', t('clients.documents.addAriaLabel'));
  fileInput.type = 'file';
  fileInput.hidden = true;

  let documents: DocumentRow[] = [];

  panel.append(list, dropButton, fileInput);
  loadDocuments();

  dropButton.addEventListener('click', () => fileInput.click());

  fileInput.addEventListener('change', async () => {
    const file = fileInput.files?.[0];
    if (!file) return;

    dropButton.disabled = true;
    dropButton.classList.add('loading');

    try {
      await uploadDocument({ clienteId: clientId, plantId }, file);
      toast.success(t('clients.documents.uploadSuccess'));
      await loadDocuments();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('clients.documents.uploadError'));
    } finally {
      dropButton.disabled = false;
      dropButton.classList.remove('loading');
      fileInput.value = '';
    }
  });

  async function loadDocuments(): Promise<void> {
    list.replaceChildren(createElement('small', { textContent: t('clients.documents.loading') }));

    try {
      documents = await getDocuments(clientId, undefined, plantId);
      renderDocuments();
    } catch {
      list.replaceChildren(createElement('small', { textContent: t('clients.documents.loadError') }));
    }
  }

  function renderDocuments(): void {
    list.replaceChildren();

    if (documents.length === 0) {
      list.appendChild(createElement('small', { textContent: t('clients.documents.empty') }));
      return;
    }

    documents.forEach((doc) => {
      const row = createElement('div', { className: 'client-document-row' });
      const name = createElement('input');
      const downloadButton = createElement('button', { className: 'secondary-button', textContent: t('clients.documents.download'), type: 'button' });
      const deleteButton = createElement('button', { className: 'icon-button', type: 'button' });

      deleteButton.appendChild(createIcon('x'));

      name.value = doc.nome;
      name.addEventListener('change', async () => {
        const novoNome = name.value.trim();

        if (!novoNome || novoNome === doc.nome) {
          name.value = doc.nome;
          return;
        }

        try {
          await renameDocument(doc.id, novoNome);
          doc.nome = novoNome;
          toast.success(t('clients.documents.renameSuccess'));
        } catch {
          toast.error(t('clients.documents.renameError'));
          name.value = doc.nome;
        }
      });

      downloadButton.addEventListener('click', () => {
        downloadDocumentFile(doc.id, doc.nome).catch(() => toast.error(t('clients.documents.downloadError')));
      });

      deleteButton.setAttribute('aria-label', `${t('clients.documents.removeAriaLabelPrefix')} ${doc.nome}`);
      deleteButton.addEventListener('click', async () => {
        if (!window.confirm(`${t('clients.documents.deleteConfirm.prefix')} "${doc.nome}"${t('clients.documents.deleteConfirm.suffix')}`)) return;

        try {
          await deleteDocument(doc.id);
          toast.success(t('clients.documents.deleteSuccess'));
          await loadDocuments();
        } catch {
          toast.error(t('clients.documents.deleteError'));
        }
      });

      row.append(name, downloadButton, deleteButton);
      list.appendChild(row);
    });
  }

  return panel;
}