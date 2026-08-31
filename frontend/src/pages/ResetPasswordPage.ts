import { createElement } from '../dom';
import { createIcon } from '../components/Icon';
import { redefinirSenha } from '../services/passwordResetService';

export function createResetPasswordPage(): HTMLElement {
  const page = createElement('section', { className: 'login-page' });
  page.style.gridTemplateColumns = '1fr';

  const formPanel = createElement('section', { className: 'login-form-panel' });
  const card = createElement('div', { className: 'login-form-card' });

  const token = new URLSearchParams(window.location.search).get('token') ?? '';

  const heading = createElement('h1', { textContent: 'Redefinir senha' });
  const subheading = createElement('p', { className: 'login-form-subtitle', textContent: 'Escolha uma nova senha pra sua conta.' });

  function goToLogin(event: Event): void {
    event.preventDefault();
    window.history.pushState({}, '', '/login');
    window.dispatchEvent(new PopStateEvent('popstate'));
  }

  if (!token) {
    const errorMsg = createElement('p', {
      className: 'login-error',
      textContent: 'Link inválido — falta o token de redefinição. Solicite um novo link.'
    });
    const backLink = createElement('a', { className: 'login-forgot-link', textContent: '← Solicitar novo link' });
    backLink.href = '/esqueci-senha';
    backLink.addEventListener('click', (event) => {
      event.preventDefault();
      window.history.pushState({}, '', '/esqueci-senha');
      window.dispatchEvent(new PopStateEvent('popstate'));
    });

    const wrapper = createElement('div', { className: 'login-view' });
    wrapper.append(heading, subheading, errorMsg, backLink);
    card.appendChild(wrapper);
    formPanel.appendChild(card);
    page.appendChild(formPanel);
    return page;
  }

  const form = createElement('form', { className: 'login-form' });

  const senhaField = createElement('label', { className: 'login-field' });
  const senhaInputWrap = createElement('div', { className: 'login-field-input' });
  const senhaInput = createElement('input');
  senhaInput.type = 'password';
  senhaInput.placeholder = '••••••••••••';
  senhaInput.required = true;
  senhaInput.minLength = 6;
  senhaInput.autocomplete = 'new-password';
  senhaInputWrap.append(createIcon('lock', 'login-field-icon'), senhaInput);
  senhaField.append(createElement('span', { className: 'login-field-label', textContent: 'Nova senha' }), senhaInputWrap);

  const confirmarField = createElement('label', { className: 'login-field' });
  const confirmarInputWrap = createElement('div', { className: 'login-field-input' });
  const confirmarInput = createElement('input');
  confirmarInput.type = 'password';
  confirmarInput.placeholder = '••••••••••••';
  confirmarInput.required = true;
  confirmarInput.autocomplete = 'new-password';
  confirmarInputWrap.append(createIcon('lock', 'login-field-icon'), confirmarInput);
  confirmarField.append(createElement('span', { className: 'login-field-label', textContent: 'Confirmar nova senha' }), confirmarInputWrap);

  const feedback = createElement('p', { className: 'login-error' });
  feedback.hidden = true;

  const submitButton = createElement('button', { className: 'login-submit-button button-with-icon', type: 'submit' });
  submitButton.append(createIcon('login'), document.createTextNode('Redefinir senha'));

  form.append(senhaField, confirmarField, feedback, submitButton);

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    feedback.hidden = true;

    if (senhaInput.value !== confirmarInput.value) {
      feedback.className = 'login-error';
      feedback.textContent = 'As senhas não coincidem.';
      feedback.hidden = false;
      return;
    }

    submitButton.disabled = true;
    submitButton.classList.add('loading');

    try {
      await redefinirSenha(token, senhaInput.value);
      const successMsg = createElement('p', {
        className: 'login-hint',
        textContent: 'Senha redefinida com sucesso! Você já pode fazer login com a nova senha.'
      });
      const loginLink = createElement('a', { className: 'login-forgot-link', textContent: 'Ir para o login' });
      loginLink.href = '/login';
      loginLink.addEventListener('click', goToLogin);
      form.replaceChildren(successMsg, loginLink);
    } catch (error) {
      feedback.className = 'login-error';
      feedback.textContent = error instanceof Error ? error.message : 'Não foi possível redefinir a senha.';
      feedback.hidden = false;
      submitButton.disabled = false;
      submitButton.classList.remove('loading');
    }
  });

  const wrapper = createElement('div', { className: 'login-view' });
  wrapper.append(heading, subheading, form);

  card.appendChild(wrapper);
  formPanel.appendChild(card);
  page.appendChild(formPanel);

  return page;
}