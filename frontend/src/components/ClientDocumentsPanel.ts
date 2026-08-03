import { createElement } from '../dom';
import { createIcon } from './Icon';
import { useToast } from '../hooks/useToast';
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
export function createClientDocumentsPanel(clientId: number | undefined): HTMLElement {
  const toast = useToast();
  const panel = createElement('div', { className: 'client-documents-panel' });
  const title = createElement('span', { className: 'plant-connection-title', textContent: 'Documentos' });

  panel.appendChild(title);

  if (!clientId) {
    panel.appendChild(createElement('p', {
      className: 'empty-state small',
      textContent: 'Salve o cliente primeiro pra poder anexar documentos.'
    }));
    return panel;
  }

  const list = createElement('div', { className: 'document-list' });
  const fileInput = createElement('input');
  const dropButton = createElement('button', { className: 'upload-dropzone', type: 'button' });

  dropButton.appendChild(createIcon('upload'));
  dropButton.setAttribute('aria-label', 'Adicionar documento');
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
      await uploadDocument({ clienteId: clientId }, file);
      toast.success('Documento enviado.');
      await loadDocuments();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Nao foi possivel enviar o documento.');
    } finally {
      dropButton.disabled = false;
      dropButton.classList.remove('loading');
      fileInput.value = '';
    }
  });

  async function loadDocuments(): Promise<void> {
    list.replaceChildren(createElement('small', { textContent: 'Carregando documentos...' }));

    try {
      documents = await getDocuments(clientId);
      renderDocuments();
    } catch {
      list.replaceChildren(createElement('small', { textContent: 'Nao foi possivel carregar os documentos.' }));
    }
  }

  function renderDocuments(): void {
    list.replaceChildren();

    if (documents.length === 0) {
      list.appendChild(createElement('small', { textContent: 'Nenhum documento anexado ainda.' }));
      return;
    }

    documents.forEach((doc) => {
      const row = createElement('div', { className: 'client-document-row' });
      const name = createElement('input');
      const downloadButton = createElement('button', { className: 'secondary-button', textContent: 'Baixar', type: 'button' });
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
          toast.success('Documento renomeado.');
        } catch {
          toast.error('Nao foi possivel renomear o documento.');
          name.value = doc.nome;
        }
      });

      downloadButton.addEventListener('click', () => {
        downloadDocumentFile(doc.id, doc.nome).catch(() => toast.error('Nao foi possivel baixar o documento.'));
      });

      deleteButton.setAttribute('aria-label', `Remover ${doc.nome}`);
      deleteButton.addEventListener('click', async () => {
        if (!window.confirm(`Excluir o documento "${doc.nome}"? Essa acao nao pode ser desfeita.`)) return;

        try {
          await deleteDocument(doc.id);
          toast.success('Documento excluido.');
          await loadDocuments();
        } catch {
          toast.error('Nao foi possivel excluir o documento.');
        }
      });

      row.append(name, downloadButton, deleteButton);
      list.appendChild(row);
    });
  }

  return panel;
}
