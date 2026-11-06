import { createElement } from '../dom';
import { createIcon } from '../components/Icon';
import { solicitarResetSenha } from '../services/passwordResetService';
import { t } from '../services/i18nService';

// Mesma casca visual do LoginPage.ts, sem a ilustracao lateral (grid vira
// 1 coluna so, ver page.style.gridTemplateColumns abaixo) -- pagina publica,
// chegada direta pela URL ou pelo link "Esqueci minha senha" no login.
export function createForgotPasswordPage(): HTMLElement {
  const page = createElement('section', { className: 'login-page' });
  page.style.gridTemplateColumns = '1fr';

  const formPanel = createElement('section', { className: 'login-form-panel' });
  const card = createElement('div', { className: 'login-form-card' });

  const heading = createElement('h1', { textContent: t('auth.forgot.heading') });
  const subheading = createElement('p', {
    className: 'login-form-subtitle',
    textContent: t('auth.forgot.subheading')
  });

  const form = createElement('form', { className: 'login-form' });
  const emailField = createElement('label', { className: 'login-field' });
  const emailInputWrap = createElement('div', { className: 'login-field-input' });
  const emailInput = createElement('input');
  emailInput.type = 'email';
  emailInput.placeholder = t('auth.login.emailPlaceholder');
  emailInput.required = true;
  emailInput.autocomplete = 'email';
  emailInputWrap.append(createIcon('user', 'login-field-icon'), emailInput);
  emailField.append(createElement('span', { className: 'login-field-label', textContent: t('auth.login.emailLabel') }), emailInputWrap);

  const feedback = createElement('p', { className: 'login-error' });
  feedback.hidden = true;

  const submitButton = createElement('button', { className: 'login-submit-button button-with-icon', type: 'submit' });
  submitButton.append(createIcon('login'), document.createTextNode(t('auth.forgot.submit')));

  form.append(emailField, feedback, submitButton);

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    feedback.hidden = true;
    submitButton.disabled = true;
    submitButton.classList.add('loading');

    try {
      const message = await solicitarResetSenha(emailInput.value.trim());
      feedback.className = 'login-hint';
      feedback.textContent = message;
      feedback.hidden = false;
      emailInput.disabled = true;
      submitButton.hidden = true;
    } catch (error) {
      feedback.className = 'login-error';
      feedback.textContent = error instanceof Error ? error.message : t('auth.forgot.genericError');
      feedback.hidden = false;
    } finally {
      submitButton.disabled = false;
      submitButton.classList.remove('loading');
    }
  });

  const backLink = createElement('a', { className: 'login-forgot-link', textContent: t('auth.backToLogin') });
  backLink.href = '/login';
  backLink.addEventListener('click', (event) => {
    event.preventDefault();
    window.history.pushState({}, '', '/login');
    window.dispatchEvent(new PopStateEvent('popstate'));
  });

  const wrapper = createElement('div', { className: 'login-view' });
  wrapper.append(heading, subheading, form, backLink);

  card.appendChild(wrapper);
  formPanel.appendChild(card);
  page.appendChild(formPanel);

  return page;
}