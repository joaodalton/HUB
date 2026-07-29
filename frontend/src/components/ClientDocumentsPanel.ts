import { createCategoryPicker } from './CategoryPicker';
import { createElement } from '../dom';
import { useToast } from '../hooks/useToast';
import {
  deleteDocument,
  downloadDocumentFile,
  getDocuments,
  renameDocument,
  uploadDocument,
  type DocumentRow
} from '../services/documentsService';

// Documentos sao acao imediata (upload/renomear/excluir acontecem na hora, via API),
// nao dependem do botao "Salvar cliente" -- diferente do que o formulario fazia antes
// (lia o arquivo como base64 e so jogava fora ao salvar, sem persistir nada de verdade).
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
  const uploadRow = createElement('div', { className: 'document-upload-row' });
  const categoryPicker = createCategoryPicker((message) => toast.error(message));
  const fileInput = createElement('input');
  const uploadButton = createElement('button', { textContent: 'Enviar', type: 'button' });

  fileInput.type = 'file';

  let documents: DocumentRow[] = [];

  uploadRow.append(categoryPicker.wrapper, fileInput, uploadButton);
  panel.append(list, uploadRow);

  loadDocuments();

  uploadButton.addEventListener('click', async () => {
    const file = fileInput.files?.[0];

    if (!file) {
      toast.error('Escolha um arquivo antes de enviar.');
      return;
    }
    if (!categoryPicker.select.value) {
      toast.error('Escolha (ou crie) uma categoria antes de enviar.');
      return;
    }

    uploadButton.disabled = true;
    uploadButton.textContent = 'Enviando...';

    try {
      await uploadDocument({ clienteId: clientId, categoriaId: Number(categoryPicker.select.value) }, file);
      toast.success('Documento enviado.');
      fileInput.value = '';
      await loadDocuments();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Nao foi possivel enviar o documento.');
    } finally {
      uploadButton.disabled = false;
      uploadButton.textContent = 'Enviar';
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
      const isDriveDoc = doc.storageProvider === 'google_drive';
      const meta = createElement('span', {
        className: 'result-meta',
        textContent: isDriveDoc ? `${doc.categoria ?? ''} - Google Drive` : (doc.categoria ?? '')
      });
      const downloadButton = createElement('button', {
        className: 'secondary-button',
        textContent: isDriveDoc ? 'Abrir no Drive' : 'Baixar',
        type: 'button'
      });
      const deleteButton = createElement('button', { className: 'icon-button', textContent: 'x', type: 'button' });

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
        if (isDriveDoc && doc.storageRef) {
          window.open(`https://drive.google.com/file/d/${doc.storageRef}/view`, '_blank', 'noopener,noreferrer');
          return;
        }

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

      row.append(name, meta, downloadButton, deleteButton);
      list.appendChild(row);
    });
  }

  return panel;
}