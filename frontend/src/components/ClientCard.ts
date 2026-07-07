import { createElement } from '../dom';
import type { ClientRow } from '../services/operationsService';

export type ClientFormData = {
  nome: string;
  cpf: string;
  email: string;
  consumo: string;
  uc: string;
  documentos: string[];
  ucs: string[];
};

type ClientCardOptions = {
  client?: ClientRow;
  onSave: (data: ClientFormData) => void;
  onCancel: () => void;
  onDelete?: () => void;
};

export function createClientCard({
  client,
  onSave,
  onCancel,
  onDelete
}: ClientCardOptions): HTMLElement {
  const isEditing = Boolean(client);
  const overlay = createElement('section', { className: 'modal-overlay' });
  const panel = createElement('article', {
    className: isEditing ? 'client-card client-card-split' : 'client-card'
  });
  const left = createElement('form', { className: 'client-form' });
  const header = createElement('div', { className: 'form-header' });
  const titleText = createElement('div');
  const eyebrow = createElement('span', {
    className: 'eyebrow',
    textContent: isEditing ? 'Cliente' : 'Novo cliente'
  });
  const heading = createElement('h2', {
    textContent: isEditing ? client?.nome ?? 'Cliente' : 'Cadastrar cliente'
  });
  const closeButton = createElement('button', {
    className: 'secondary-button',
    textContent: 'Fechar',
    type: 'button'
  });
  const fields = createElement('div', { className: 'form-grid' });
  const nome = createInput('Nome', 'text', client?.nome ?? '', true);
  const cpf = createInput('CPF', 'text', client?.cpf ?? '', true);
  const email = createInput('Email', 'email', client?.email ?? '', true);
  const consumo = createInput('Consumo', 'text', client?.consumo ?? '', false);
  const uc = createInput('UC principal', 'text', client?.uc ?? '', false);
  const documents = createDocumentPicker(client?.documentos ?? []);
  const actions = createElement('div', { className: 'form-actions' });
  const saveButton = createElement('button', { textContent: 'Salvar cliente', type: 'submit' });

  titleText.append(eyebrow, heading);
  header.append(titleText, closeButton);
  fields.append(nome.field, cpf.field, email.field, consumo.field, uc.field, documents.field);
  actions.appendChild(saveButton);

  if (isEditing && onDelete) {
    const deleteButton = createElement('button', {
      className: 'danger-button',
      textContent: 'Excluir cliente',
      type: 'button'
    });

    deleteButton.addEventListener('click', onDelete);
    actions.appendChild(deleteButton);
  }

  closeButton.addEventListener('click', onCancel);
  left.addEventListener('submit', (event) => {
    event.preventDefault();

    if (!nome.input.value.trim() || !cpf.input.value.trim() || !email.input.value.trim()) {
      nome.input.reportValidity();
      cpf.input.reportValidity();
      email.input.reportValidity();
      return;
    }

    const selectedDocuments = Array.from(documents.input.files ?? []).map((file) => file.name);
    const mergedDocuments = Array.from(new Set([...documents.currentDocuments, ...selectedDocuments]));
    const mainUc = uc.input.value.trim();

    onSave({
      nome: nome.input.value.trim(),
      cpf: cpf.input.value.trim(),
      email: email.input.value.trim(),
      consumo: consumo.input.value.trim(),
      uc: mainUc,
      documentos: mergedDocuments,
      ucs: client?.ucs?.length ? client.ucs : mainUc ? [mainUc] : []
    });
  });

  left.append(header, fields, actions);
  panel.appendChild(left);

  if (isEditing) {
    panel.appendChild(createUcPanel(client));
  }

  overlay.appendChild(panel);
  return overlay;
}

function createInput(label: string, type: string, value: string, required: boolean) {
  const field = createElement('label', { className: 'form-field' });
  const text = createElement('span', { textContent: label });
  const input = createElement('input');

  input.type = type;
  input.value = value;
  input.required = required;

  field.append(text, input);
  return { field, input };
}

function createDocumentPicker(currentDocuments: string[]) {
  const field = createElement('label', { className: 'form-field form-field-wide' });
  const text = createElement('span', { textContent: 'Documentos' });
  const input = createElement('input');
  const hint = createElement('small', {
    textContent: currentDocuments.length
      ? `Anexados: ${currentDocuments.join(', ')}`
      : 'Nenhum documento anexado ainda.'
  });

  input.type = 'file';
  input.multiple = true;

  field.append(text, input, hint);
  return { field, input, currentDocuments };
}

function createUcPanel(client: ClientRow): HTMLElement {
  const panel = createElement('aside', { className: 'client-uc-panel' });
  const title = createElement('div', { className: 'panel-title' });
  const titleText = createElement('div');
  const eyebrow = createElement('span', { className: 'eyebrow', textContent: 'UCs' });
  const heading = createElement('h2', { textContent: 'Unidades consumidoras' });
  const list = createElement('ul', { className: 'uc-list' });
  const items = client.ucs.length ? client.ucs : client.uc ? [client.uc] : [];

  titleText.append(eyebrow, heading);
  title.appendChild(titleText);

  if (items.length === 0) {
    list.appendChild(createElement('li', { className: 'empty-state small', textContent: 'Nenhuma UC vinculada.' }));
  } else {
    items.forEach((uc) => {
      const item = createElement('li', { className: 'uc-row' });
      const code = createElement('strong', { textContent: uc });
      const meta = createElement('span', { textContent: client.usina });

      item.append(code, meta);
      list.appendChild(item);
    });
  }

  panel.append(title, list);
  return panel;
}
