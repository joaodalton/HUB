// frontend/src/components/DocumentLinkModal.ts
import { createCategoryPicker } from './CategoryPicker';
import { createElement } from '../dom';
import type { ClientRow } from '../services/clientsService';
import { linkDriveDocument } from '../services/documentsService';
import type { DriveItem } from '../types';

type DocumentLinkModalOptions = {
  files: DriveItem[];
  clients: ClientRow[];
  onLinked: (linkedFileIds: string[]) => void;
  onError: (message: string) => void;
};

export function createDocumentLinkModal({ files, clients, onLinked, onError }: DocumentLinkModalOptions): HTMLElement {
  const overlay = createElement('section', { className: 'modal-overlay' });
  const panel = createElement('article', { className: 'client-card' });
  const form = createElement('form', { className: 'client-form' });
  const header = createElement('div', { className: 'form-header' });
  const titleText = createElement('div');
  const eyebrow = createElement('span', { className: 'eyebrow', textContent: 'Vincular documentos' });
  const heading = createElement('h2', {
    textContent: `${files.length} ${files.length === 1 ? 'arquivo selecionado' : 'arquivos selecionados'}`
  });
  const closeButton = createElement('button', { className: 'secondary-button', textContent: 'Fechar', type: 'button' });

  const fileList = createElement('ul', { className: 'document-list' });
  files.forEach((file) => {
    fileList.appendChild(createElement('li', { textContent: file.name }));
  });

  const clientField = createElement('label', { className: 'form-field form-field-wide' });
  const clientLabel = createElement('span', { textContent: 'Cliente' });
  const clientSelect = createElement('select');
  const placeholder = createElement('option', { textContent: 'Selecione um cliente' });
  placeholder.value = '';
  clientSelect.appendChild(placeholder);
  clients.forEach((client) => {
    const option = createElement('option', { textContent: client.nome });
    option.value = String(client.id);
    clientSelect.appendChild(option);
  });
  clientSelect.required = true;
  clientField.append(clientLabel, clientSelect);

  const categoryField = createElement('label', { className: 'form-field form-field-wide' });
  const categoryLabel = createElement('span', { textContent: 'Categoria' });
  const categoryPicker = createCategoryPicker(onError);
  categoryField.append(categoryLabel, categoryPicker.wrapper);

  const actions = createElement('div', { className: 'form-actions' });
  const saveButton = createElement('button', { textContent: 'Vincular', type: 'submit' });

  closeButton.addEventListener('click', () => overlay.remove());
  overlay.addEventListener('click', (event) => {
    if (event.target === overlay) overlay.remove();
  });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();

    if (!clientSelect.value) {
      clientSelect.reportValidity();
      return;
    }
    if (!categoryPicker.select.value) {
      onError('Escolha (ou crie) uma categoria antes de vincular.');
      return;
    }

    saveButton.disabled = true;
    saveButton.textContent = 'Vinculando...';

    const clienteId = Number(clientSelect.value);
    const categoriaId = Number(categoryPicker.select.value);
    const linked: string[] = [];

    for (const file of files) {
      try {
        await linkDriveDocument({
          clienteId,
          categoriaId,
          nome: file.name,
          driveFileId: file.id,
          mimeType: file.mimeType
        });
        linked.push(file.id);
      } catch (error) {
        onError(error instanceof Error ? error.message : `Nao foi possivel vincular "${file.name}".`);
      }
    }

    if (linked.length > 0) onLinked(linked);
    overlay.remove();
  });

  titleText.append(eyebrow, heading);
  header.append(titleText, closeButton);
  form.append(header, fileList, clientField, categoryField, actions);
  actions.appendChild(saveButton);
  panel.appendChild(form);
  overlay.appendChild(panel);

  return overlay;
}