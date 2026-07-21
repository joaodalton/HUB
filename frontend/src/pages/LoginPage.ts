import { createElement } from '../dom';
import { login } from '../services/authService';

export function createLoginPage(onSuccess: () => void): HTMLElement {
  const wrapper = createElement('section', { className: 'login-page' });
  const card = createElement('article', { className: 'login-card' });
  const brand = createElement('div', { className: 'login-brand' });
  const brandMark = createElement('span', { className: 'sidebar-mark', textContent: 'H' });
  const brandText = createElement('span', { textContent: 'APP HUB' });
  const form = createElement('form', { className: 'client-form' });
  const fields = createElement('div', { className: 'form-grid' });
  const emailField = createLoginInput('Email', 'email');
  const senhaField = createLoginInput('Senha', 'password');
  const actions = createElement('div', { className: 'form-actions' });
  const submitButton = createElement('button', { textContent: 'Entrar', type: 'submit' });
  const errorText = createElement('p', { className: 'login-error' });

  errorText.hidden = true;

  brand.append(brandMark, brandText);
  fields.append(emailField.field, senhaField.field);
  actions.appendChild(submitButton);

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    errorText.hidden = true;
    submitButton.disabled = true;
    submitButton.textContent = 'Entrando...';

    try {
      await login(emailField.input.value.trim(), senhaField.input.value);
      onSuccess();
    } catch (error) {
      errorText.textContent = error instanceof Error ? error.message : 'Nao foi possivel entrar.';
      errorText.hidden = false;
    } finally {
      submitButton.disabled = false;
      submitButton.textContent = 'Entrar';
    }
  });

  form.append(fields, errorText, actions);
  card.append(brand, form);
  wrapper.appendChild(card);

  return wrapper;
}

function createLoginInput(label: string, type: string) {
  const field = createElement('label', { className: 'form-field form-field-wide' });
  const text = createElement('span', { textContent: label });
  const input = createElement('input');

  input.type = type;
  input.required = true;
  input.autocomplete = type === 'password' ? 'current-password' : 'email';

  field.append(text, input);
  return { field, input };
}