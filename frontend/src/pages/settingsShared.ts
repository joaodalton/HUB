import { createElement } from '../dom';
import { getCurrentUser } from '../services/authService';

// ---------- Helpers compartilhados ----------

export function createPanelHeader(eyebrowText: string, title: string, action?: HTMLElement): HTMLElement {
  const header = createElement('div', { className: 'panel-title' });
  const titleText = createElement('div');
  const eyebrow = createElement('span', { className: 'eyebrow', textContent: eyebrowText });
  const heading = createElement('h2', { textContent: title });

  titleText.append(eyebrow, heading);
  header.appendChild(titleText);
  if (action) header.appendChild(action);

  return header;
}

export function canManageSettings(): boolean {
  const role = getCurrentUser()?.role;
  return role === 'owner' || role === 'admin';
}

export function isPlatformAdmin(): boolean {
  return getCurrentUser()?.isPlatformAdmin === true;
}

export function createToggle(label: string, checked: boolean): { field: HTMLElement; checked: boolean } {
  const field = createElement('label', { className: 'form-field form-field-checkbox' });
  const input = createElement('input');
  input.type = 'checkbox';
  input.checked = checked;
  field.append(input, createElement('span', { textContent: label }));
  return { field, get checked() { return input.checked; }, set checked(value: boolean) { input.checked = value; } };
}
