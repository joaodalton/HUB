import { createElement } from '../dom';
import { createClientDocumentsPanel } from './ClientDocumentsPanel';
import { createFormSection, createInput, createSelect } from './formFields';
import { cnpjError, cpfError, digits, maskCpfInput, phoneDigits, phoneError, ucError, validateField } from './cadastroFields';
import { createUcPanel } from './ClientCardUcEditor';
import { concessionarias, type ClientRow, type ClientUc } from '../services/clientsService';
import type { PlantRow } from '../services/plantService';
import { t } from '../services/i18nService';

export type ClientFormData = {
  nome: string;
  cpf: string;
  email: string;
  telefone: string;
  dataNascimento: string;
  concessionaria: string;
  ucs: ClientUc[];
};

type ClientCardOptions = {
  client?: ClientRow;
  availablePlants: PlantRow[];
  onSave: (data: ClientFormData) => void;
  onCancel: () => void;
  onDelete?: () => void;
};

export function createClientCard({
  client,
  availablePlants,
  onSave,
  onCancel,
  onDelete
}: ClientCardOptions): HTMLElement {
  const isEditing = Boolean(client);
  const currentUcs = [...(client?.ucs ?? [])];
  const originalUcs = new Map((client?.ucs ?? []).map((uc) => [uc.id, { codigo: uc.codigo, concessionaria: uc.concessionaria }]));
  const overlay = createElement('section', { className: 'modal-overlay' });
  const panel = createElement('article', {
    className: isEditing ? 'client-card client-card-split' : 'client-card'
  });
  const left = createElement('form', { className: 'client-form' });
  const header = createElement('div', { className: 'form-header' });
  const titleText = createElement('div');
  const eyebrow = createElement('span', {
    className: 'eyebrow',
    textContent: isEditing ? t('clients.card.eyebrowEdit') : t('clients.card.eyebrowNew')
  });
  const heading = createElement('h2', {
    textContent: isEditing ? client?.nome ?? t('clients.card.headingFallback') : t('clients.card.headingNew')
  });
  const closeButton = createElement('button', {
    className: 'secondary-button',
    textContent: t('shared.modal.close'),
    type: 'button'
  });
  const nome = createInput(t('clients.card.fieldName'), 'text', client?.nome ?? '', true);
  const cpf = createInput(t('clients.card.fieldCpf'), 'text', client?.cpf ?? '', true);
  const telefone = createInput(t('clients.card.fieldPhone'), 'tel', client?.telefone ?? '', false);
  const email = createInput(t('clients.card.fieldEmail'), 'email', client?.email ?? '', true);
  const dataNascimento = createInput(t('clients.card.fieldBirthDate'), 'date', client?.dataNascimento ?? '', false);
  const concessionaria = createSelect(t('clients.card.fieldUtility'), client?.concessionaria ?? concessionarias[0], concessionarias);
  nome.input.maxLength = 200;
  nome.input.addEventListener('input', () => validateField(nome.input, ''));
  maskCpfInput(cpf.input);
  cpf.input.addEventListener('input', () => validateField(cpf.input, ''));
  telefone.input.addEventListener('input', () => validateField(telefone.input, ''));
  const documentsPanel = createClientDocumentsPanel(client?.id);
  const actions = createElement('div', { className: 'form-actions' });
  const saveButton = createElement('button', { textContent: t('clients.card.saveButton'), type: 'submit' });
  const ucPanel = createUcPanel(currentUcs, availablePlants);
  concessionaria.select.addEventListener('change', () => ucPanel.querySelectorAll<HTMLInputElement>('[data-uc-code]')
    .forEach((input) => validateField(input, '')));

  titleText.append(eyebrow, heading);
  header.append(titleText, closeButton);
  actions.appendChild(saveButton);

  if (isEditing && onDelete) {
    const deleteButton = createElement('button', {
      className: 'danger-button',
      textContent: t('clients.card.deleteButton'),
      type: 'button'
    });

    deleteButton.addEventListener('click', onDelete);
    actions.appendChild(deleteButton);
  }

  let isSubmitting = false;

  closeButton.addEventListener('click', onCancel);
  left.addEventListener('submit', async (event) => {
    event.preventDefault();

    if (isSubmitting) return;

    if (!validateField(nome.input, nome.input.value.trim() ? '' : 'Informe o nome.') ||
        !validateField(cpf.input, client && digits(cpf.input.value) === digits(client.cpf) ? '' : cpfError(cpf.input.value)) ||
        (telefone.input.value.trim() && !validateField(telefone.input,
          client && telefone.input.value === (client.telefone ?? '') ? '' : phoneError(telefone.input.value))) ||
        !email.input.value.trim()) {
      nome.input.reportValidity();
      cpf.input.reportValidity();
      email.input.reportValidity();
      return;
    }
    const invalidUc = [...ucPanel.querySelectorAll<HTMLInputElement>('[data-uc-code]')].find((input) => {
      if (!input.value.trim() && input.dataset.existingUc !== 'true') return false;
      if (input.value === input.dataset.originalValue &&
          input.dataset.concessionaria === input.dataset.originalConcessionaria) return false;
      return !validateField(input, input.value.trim() ?
        ucError(input.value, input.dataset.concessionaria || concessionaria.select.value) : 'Informe a UC.');
    });
    if (invalidUc) { invalidUc.closest('details')?.setAttribute('open', ''); return; }
    const invalidDocument = [...ucPanel.querySelectorAll<HTMLInputElement>('[data-uc-document]')].find((input) =>
      input.value.trim() && input.value !== input.dataset.originalValue && !validateField(input,
        digits(input.value).length === 11 ? cpfError(input.value) : cnpjError(input.value)));
    if (invalidDocument) { invalidDocument.closest('details')?.setAttribute('open', ''); return; }
    currentUcs.forEach((uc) => {
      const original = originalUcs.get(uc.id);
      if ((!original || original.codigo !== uc.codigo || original.concessionaria !== uc.concessionaria) &&
          (uc.concessionaria || concessionaria.select.value).trim().toLowerCase() === 'copel' && /^\d{12}$/.test(uc.codigo)) uc.codigo = `000${uc.codigo}`;
    });

    isSubmitting = true;
    saveButton.disabled = true;
    saveButton.textContent = t('common.saving');

    onSave({
      nome: nome.input.value.trim(),
      cpf: digits(cpf.input.value),
      email: email.input.value.trim(),
      telefone: telefone.input.value.trim() ? (client && telefone.input.value === (client.telefone ?? '')
        ? telefone.input.value : phoneDigits(telefone.input.value)) : '',
      dataNascimento: dataNascimento.input.value,
      concessionaria: concessionaria.select.value,
      ucs: currentUcs.filter((uc) => uc.codigo.trim())
    });
  });

  left.append(
    header,
    createFormSection(t('clients.card.sectionMain'), nome.field, cpf.field, telefone.field, email.field, dataNascimento.field),
    createFormSection(t('clients.card.sectionUtility'), concessionaria.field),
    documentsPanel,
    actions
  );
  panel.appendChild(left);

  panel.appendChild(ucPanel);

  overlay.addEventListener('click', (event) => {
    if (event.target === overlay) onCancel();
  });

  overlay.appendChild(panel);
  return overlay;
}

