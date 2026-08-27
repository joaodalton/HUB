// frontend/src/components/formFields.ts
// Helpers de campo de formulario reaproveitados por ClientCard, UcCard e
// PlantCard -- os tres tinham copia identica de createInput/createSelect.
// Nao duplicar de novo em outro componente, importar daqui.
import { createElement } from '../dom';

export function createInput(label: string, type: string, value: string, required = false) {
  const field = createElement('label', { className: 'form-field' });
  const text = createElement('span', { textContent: label });
  const input = createElement('input');

  input.type = type;
  input.value = value;
  input.required = required;

  field.append(text, input);
  return { field, input };
}

export function createSelect<T extends string>(label: string, value: T, options: T[]) {
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

// Campo de checkbox (ex.: "Geracao propria" da UC) -- layout em linha
// (checkbox + texto ao lado), diferente do .form-field padrao que empilha
// label em cima do input.
export function createCheckboxField(label: string, checked: boolean) {
  const field = createElement('label', { className: 'form-field form-field-checkbox' });
  const input = createElement('input');
  const text = createElement('span', { textContent: label });

  input.type = 'checkbox';
  input.checked = checked;

  field.append(input, text);
  return { field, input };
}

// Par valor/rotulo (ex.: mostrar "Visualizador (so leitura)" mas gravar
// "viewer") -- createSelect acima serve quando rotulo e valor sao iguais;
// use este quando precisar dissociar os dois. Movido de SettingsPage.ts
// (era cópia local, agora reaproveitado tambem por UsersPage.ts).
export function createSelectField(
  label: string,
  value: string,
  options: Array<{ value: string; label: string }>
) {
  const field = createElement('label', { className: 'form-field' });
  const text = createElement('span', { textContent: label });
  const select = createElement('select');

  options.forEach((option) => {
    const optionElement = createElement('option', { textContent: option.label });
    optionElement.value = option.value;
    select.appendChild(optionElement);
  });

  select.value = value;
  field.append(text, select);
  return { field, select };
}