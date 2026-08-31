import { createIcon } from '../components/Icon';
import { createElement } from '../dom';
import { alterarSenhaObrigatoria, refreshCurrentUser } from '../services/authService';

export function createChangePasswordPage(): HTMLElement {
  const page = createElement('section', { className: 'login-page' });
  page.style.gridTemplateColumns = '1fr';
  const formPanel = createElement('section', { className: 'login-form-panel' });
  const card = createElement('div', { className: 'login-form-card' });
  const wrapper = createElement('div', { className: 'login-view' });
  const form = createElement('form', { className: 'login-form' });
  const feedback = createElement('p', { className: 'login-error' }); feedback.hidden = true;
  const current = createPasswordField('Senha temporária atual', 'current-password');
  const next = createPasswordField('Nova senha', 'new-password'); next.input.minLength = 6;
  const confirmation = createPasswordField('Confirmar nova senha', 'new-password'); confirmation.input.minLength = 6;
  const submit = createElement('button', { className: 'login-submit-button button-with-icon', type: 'submit' });
  submit.append(createIcon('lock'), document.createTextNode('Atualizar senha'));
  form.append(current.field, next.field, confirmation.field, feedback, submit);
  wrapper.append(
    createElement('h1', { textContent: 'Atualize sua senha' }),
    createElement('p', { className: 'login-form-subtitle', textContent: 'Por segurança, troque a senha temporária antes de continuar.' }),
    form
  );
  card.appendChild(wrapper); formPanel.appendChild(card); page.appendChild(formPanel);
  form.addEventListener('submit', async (event) => {
    event.preventDefault(); feedback.hidden = true;
    if (!form.reportValidity()) return;
    if (next.input.value !== confirmation.input.value) { showError('As novas senhas não coincidem.'); return; }
    if (current.input.value === next.input.value) { showError('Escolha uma nova senha diferente da temporária.'); return; }
    submit.disabled = true; submit.classList.add('loading');
    try {
      await alterarSenhaObrigatoria(current.input.value, next.input.value);
      current.input.value = ''; next.input.value = ''; confirmation.input.value = '';
      const user = await refreshCurrentUser();
      if (user?.mustChangePassword) throw new Error('A troca não foi confirmada. Tente novamente.');
      window.history.replaceState({}, '', '/dashboard');
      window.dispatchEvent(new PopStateEvent('popstate'));
    } catch (error) {
      showError(error instanceof Error ? error.message : 'Não foi possível atualizar a senha.');
      submit.disabled = false; submit.classList.remove('loading');
    }
  });
  return page;
  function showError(message: string): void { feedback.textContent = message; feedback.hidden = false; }
}

function createPasswordField(label: string, autocomplete: string): { field: HTMLLabelElement; input: HTMLInputElement } {
  const field = createElement('label', { className: 'login-field' });
  const wrap = createElement('div', { className: 'login-field-input' });
  const input = createElement('input'); input.type = 'password'; input.required = true; input.setAttribute('autocomplete', autocomplete); input.placeholder = '••••••••••••';
  wrap.append(createIcon('lock', 'login-field-icon'), input);
  field.append(createElement('span', { className: 'login-field-label', textContent: label }), wrap);
  return { field, input };
}
