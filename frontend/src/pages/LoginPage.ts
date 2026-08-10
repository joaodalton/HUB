import { createElement } from '../dom';
import { login, register } from '../services/authService';

type Mode = 'login' | 'register';

export function createLoginPage(onSuccess: () => void): HTMLElement {
  const wrapper = createElement('section', { className: 'login-page' });
  const card = createElement('article', { className: 'login-card' });
  const brand = createElement('div', { className: 'login-brand' });
  const brandMark = createElement('span', { className: 'sidebar-mark', textContent: 'H' });
  const brandText = createElement('span', { textContent: 'APP HUB' });
  const formHolder = createElement('div');

  brand.append(brandMark, brandText);

  let mode: Mode = 'login';

  function render(): void {
    formHolder.replaceChildren(mode === 'login' ? createLoginForm() : createRegisterForm());
  }

  function createLoginForm(): HTMLElement {
    const form = createElement('form', { className: 'client-form' });
    const fields = createElement('div', { className: 'form-grid' });
    const emailField = createLoginInput('Email', 'email');
    const senhaField = createLoginInput('Senha', 'password');
    const actions = createElement('div', { className: 'form-actions' });
    const submitButton = createElement('button', { textContent: 'Entrar', type: 'submit' });
    const errorText = createElement('p', { className: 'login-error' });
    const switchLink = createElement('button', {
      className: 'secondary-link',
      textContent: 'Criar uma conta',
      type: 'button'
    });

    errorText.hidden = true;

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

    switchLink.addEventListener('click', () => {
      mode = 'register';
      render();
    });

    form.append(fields, errorText, actions, switchLink);
    return form;
  }

  function createRegisterForm(): HTMLElement {
    const form = createElement('form', { className: 'client-form' });
    const fields = createElement('div', { className: 'form-grid' });
    const emailField = createLoginInput('Email', 'email');
    const senhaField = createLoginInput('Senha', 'password');
    const codigoField = createLoginInput('Código de acesso', 'text');
    const actions = createElement('div', { className: 'form-actions' });
    const submitButton = createElement('button', { textContent: 'Criar conta', type: 'submit' });
    const errorText = createElement('p', { className: 'login-error' });
    const hint = createElement('p', {
      className: 'settings-hint',
      textContent: 'A conta criada aqui vem sempre como "somente leitura". Peça o código de acesso a quem administra o HUB.'
    });
    const switchLink = createElement('button', {
      className: 'secondary-link',
      textContent: 'Já tenho conta',
      type: 'button'
    });

    errorText.hidden = true;

    fields.append(emailField.field, senhaField.field, codigoField.field);
    actions.appendChild(submitButton);

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      errorText.hidden = true;
      submitButton.disabled = true;
      submitButton.textContent = 'Criando...';

      try {
        await register(emailField.input.value.trim(), senhaField.input.value, codigoField.input.value.trim());
        await login(emailField.input.value.trim(), senhaField.input.value);
        onSuccess();
      } catch (error) {
        errorText.textContent = error instanceof Error ? error.message : 'Nao foi possivel criar a conta.';
        errorText.hidden = false;
      } finally {
        submitButton.disabled = false;
        submitButton.textContent = 'Criar conta';
      }
    });

    switchLink.addEventListener('click', () => {
      mode = 'login';
      render();
    });

    form.append(fields, hint, errorText, actions, switchLink);
    return form;
  }

  render();

  card.append(brand, formHolder);
  wrapper.appendChild(card);

  return wrapper;
}

function createLoginInput(label: string, type: string) {
  const field = createElement('label', { className: 'form-field form-field-wide' });
  const text = createElement('span', { textContent: label });
  const input = createElement('input');

  input.type = type;
  input.required = true;
  input.autocomplete = type === 'password' ? 'current-password' : type === 'email' ? 'email' : 'off';

  field.append(text, input);
  return { field, input };
}