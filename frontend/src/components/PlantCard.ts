import { createElement } from '../dom';
import type { PlantRow } from '../services/operationsService';

export type PlantFormData = {
  nome: string;
  uc: string;
  kwPico: string;
  status: string;
  percentualDisponivel: number;
};

type PlantCardOptions = {
  plant?: PlantRow;
  onSave: (data: PlantFormData) => void;
  onCancel: () => void;
  onDelete?: () => void;
};

const plantStatuses = ['Online', 'Implantacao', 'Manutencao', 'Inativa'];

export function createPlantCard({ plant, onSave, onCancel, onDelete }: PlantCardOptions): HTMLElement {
  const overlay = createElement('section', { className: 'modal-overlay' });
  const panel = createElement('article', { className: 'plant-card' });
  const form = createElement('form', { className: 'client-form' });
  const header = createElement('div', { className: 'form-header' });
  const titleText = createElement('div');
  const eyebrow = createElement('span', { className: 'eyebrow', textContent: plant ? 'Usina' : 'Nova usina' });
  const heading = createElement('h2', { textContent: plant?.nome ?? 'Cadastrar usina' });
  const closeButton = createElement('button', {
    className: 'secondary-button',
    textContent: 'Fechar',
    type: 'button'
  });
  const fields = createElement('div', { className: 'form-grid' });
  const nome = createInput('Nome', 'text', plant?.nome ?? '', true);
  const uc = createInput('UC', 'text', plant?.uc ?? '', true);
  const kwPico = createInput('kW pico', 'number', plant?.kwPico ?? '', true);
  const status = createSelect('Status', plant?.status ?? 'Online', plantStatuses);
  const percentualDisponivel = createInput(
    'Disponivel para rateio (%)',
    'number',
    String(plant?.percentualDisponivel ?? 0),
    true
  );
  const actions = createElement('div', { className: 'form-actions' });
  const saveButton = createElement('button', { textContent: 'Salvar usina', type: 'submit' });

  kwPico.input.min = '0';
  percentualDisponivel.input.min = '0';
  percentualDisponivel.input.max = '100';

  titleText.append(eyebrow, heading);
  header.append(titleText, closeButton);
  fields.append(nome.field, uc.field, kwPico.field, status.field, percentualDisponivel.field);
  actions.appendChild(saveButton);

  if (plant && onDelete) {
    const deleteButton = createElement('button', {
      className: 'danger-button',
      textContent: 'Excluir usina',
      type: 'button'
    });

    deleteButton.addEventListener('click', onDelete);
    actions.appendChild(deleteButton);
  }

  closeButton.addEventListener('click', onCancel);
  overlay.addEventListener('click', (event) => {
    if (event.target === overlay) onCancel();
  });
  form.addEventListener('submit', (event) => {
    event.preventDefault();

    if (!nome.input.value.trim() || !uc.input.value.trim() || !kwPico.input.value.trim()) {
      nome.input.reportValidity();
      uc.input.reportValidity();
      kwPico.input.reportValidity();
      return;
    }

    onSave({
      nome: nome.input.value.trim(),
      uc: uc.input.value.trim(),
      kwPico: kwPico.input.value.trim(),
      status: status.select.value,
      percentualDisponivel: clampPercent(Number(percentualDisponivel.input.value))
    });
  });

  form.append(header, fields, actions);
  panel.appendChild(form);
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

function createSelect(label: string, value: string, options: string[]) {
  const field = createElement('label', { className: 'form-field' });
  const text = createElement('span', { textContent: label });
  const select = createElement('select');

  options.forEach((optionValue) => {
    const option = createElement('option', { textContent: optionValue });
    option.value = optionValue;
    select.appendChild(option);
  });

  select.value = value;
  field.append(text, select);

  return { field, select };
}

function clampPercent(value: number): number {
  if (Number.isNaN(value)) return 0;
  return Math.min(100, Math.max(0, value));
}
