// frontend/src/components/DocumentLinkModal.ts
import { createCategoryPicker } from './CategoryPicker';
import { createElement } from '../dom';
import type { ClientRow } from '../services/clientsService';
import { linkDriveDocument } from '../services/documentsService';
import { t } from '../services/i18nService';
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
  const eyebrow = createElement('span', { className: 'eyebrow', textContent: t('documents.linkModal.eyebrow') });
  const heading = createElement('h2', {
    textContent: `${files.length} ${files.length === 1 ? t('documents.linkModal.fileSingular') : t('documents.linkModal.filePlural')}`
  });
  const closeButton = createElement('button', { className: 'secondary-button', textContent: t('documents.linkModal.close'), type: 'button' });

  const fileList = createElement('ul', { className: 'document-list' });
  files.forEach((file) => {
    fileList.appendChild(createElement('li', { textContent: file.name }));
  });

  const clientField = createElement('label', { className: 'form-field form-field-wide' });
  const clientLabel = createElement('span', { textContent: t('documents.linkModal.clientLabel') });
  const clientSelect = createElement('select');
  const placeholder = createElement('option', { textContent: t('documents.linkModal.clientPlaceholder') });
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
  const categoryLabel = createElement('span', { textContent: t('documents.linkModal.categoryLabel') });
  const categoryPicker = createCategoryPicker(onError);
  categoryField.append(categoryLabel, categoryPicker.wrapper);

  const actions = createElement('div', { className: 'form-actions' });
  const saveButton = createElement('button', { textContent: t('documents.linkModal.save'), type: 'submit' });

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
      onError(t('documents.linkModal.categoryRequired'));
      return;
    }

    saveButton.disabled = true;
    saveButton.textContent = t('documents.linkModal.saving');

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
        onError(error instanceof Error ? error.message : `${t('documents.linkModal.linkErrorPrefix')} "${file.name}".`);
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