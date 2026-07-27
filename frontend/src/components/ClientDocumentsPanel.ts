import { createElement } from '../dom';
import { useToast } from '../hooks/useToast';
import {
  createCategory,
  deleteDocument,
  downloadDocumentFile,
  getCategories,
  getDocuments,
  renameDocument,
  uploadDocument,
  type CategoryRow,
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
  const categorySelect = createElement('select');
  const newCategoryButton = createElement('button', {
    className: 'secondary-button',
    textContent: '+ categoria',
    type: 'button'
  });
  const fileInput = createElement('input');
  const uploadButton = createElement('button', { textContent: 'Enviar', type: 'button' });

  fileInput.type = 'file';

  let documents: DocumentRow[] = [];
  let categories: CategoryRow[] = [];

  uploadRow.append(categorySelect, newCategoryButton, fileInput, uploadButton);
  panel.append(list, uploadRow);

  loadCategories();
  loadDocuments();

  uploadButton.addEventListener('click', async () => {
    const file = fileInput.files?.[0];

    if (!file) {
      toast.error('Escolha um arquivo antes de enviar.');
      return;
    }
    if (!categorySelect.value) {
      toast.error('Escolha (ou crie) uma categoria antes de enviar.');
      return;
    }

    uploadButton.disabled = true;
    uploadButton.textContent = 'Enviando...';

    try {
      await uploadDocument({ clienteId: clientId, categoriaId: Number(categorySelect.value) }, file);
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

  newCategoryButton.addEventListener('click', async () => {
    const nome = window.prompt('Nome da categoria (ex: Termo de adesao, Fatura, Contrato):');
    if (!nome || !nome.trim()) return;

    try {
      const category = await createCategory(nome.trim());
      categories = [...categories, category];
      renderCategoryOptions();
      categorySelect.value = String(category.id);
      toast.success('Categoria criada.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Nao foi possivel criar a categoria.');
    }
  });

  async function loadCategories(): Promise<void> {
    try {
      categories = await getCategories();
    } catch {
      categories = [];
    } finally {
      renderCategoryOptions();
    }
  }

  function renderCategoryOptions(): void {
    categorySelect.replaceChildren();

    const placeholder = createElement('option', {
      textContent: categories.length === 0 ? 'Nenhuma categoria ainda' : 'Categoria...'
    });
    placeholder.value = '';
    categorySelect.appendChild(placeholder);

    categories.forEach((category) => {
      const option = createElement('option', { textContent: category.nome });
      option.value = String(category.id);
      categorySelect.appendChild(option);
    });
  }

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
      const meta = createElement('span', { className: 'result-meta', textContent: doc.categoria ?? '' });
      const downloadButton = createElement('button', {
        className: 'secondary-button',
        textContent: 'Baixar',
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
