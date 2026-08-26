// frontend/src/components/formFields.ts
// Helpers de campo de formulário reaproveitados por vários componentes.

import { createElement } from '../dom';

export function createInput(
  label: string,
  type: string,
  value: string,
  required = false
): { field: HTMLElement; input: HTMLInputElement } {
  const field = createElement('label', { className: 'form-field' });
  const text = createElement('span', { textContent: label });
  const input = createElement('input', {
    type,
    value,
    required
  });
  field.append(text, input);
  return { field, input: input as HTMLInputElement };
}

export function createSelect<T extends string>(
  label: string,
  value: T,
  options: T[]
): { field: HTMLElement; select: HTMLSelectElement } {
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
  return { field, select: select as HTMLSelectElement };
}

export function createCheckboxField(label: string, checked = false): { field: HTMLElement; input: HTMLInputElement } {
  const field = createElement('label', { className: 'form-field form-field-checkbox' });
  const input = createElement('input');
  const text = createElement('span', { textContent: label });

  input.type = 'checkbox';
  input.checked = checked;

  field.append(input, text);
  return { field, input };
}

export function createSelectField(
  label: string,
  value: string,
  options: Array<{ value: string; label: string }>
): { field: HTMLElement; select: HTMLSelectElement } {
  const field = createElement('label', { className: 'form-field' });
  const text = createElement('span', { textContent: label });
  const select = createElement('select');

  options.forEach((option) => {
    const optionEl = createElement('option', { textContent: option.label });
    optionEl.value = option.value;
    select.appendChild(optionEl);
  });

  select.value = value;
  field.append(text, select);
  return { field, select: select as HTMLSelectElement };
}
