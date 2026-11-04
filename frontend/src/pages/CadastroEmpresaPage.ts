import { createElement } from '../dom';
import { createIcon } from '../components/Icon';
import { concluirCadastroPedidoPlano } from '../services/pedidoPlanoService';
import { t } from '../services/i18nService';

// Pagina publica que consome o token emitido apos confirmacao do pagamento
// (ver POST /platform/pedidos-plano/concluir) -- mesma casca do
// ResetPasswordPage.ts (token na query string, erro se ausente).
export function createCadastroEmpresaPage(): HTMLElement {
  const page = createElement('section', { className: 'login-page' });
  page.style.gridTemplateColumns = '1fr';

  const formPanel = createElement('section', { className: 'login-form-panel' });
  const card = createElement('div', { className: 'login-form-card' });

  const token = new URLSearchParams(window.location.search).get('token') ?? '';

  const heading = createElement('h1', { textContent: t('auth.cadastroEmpresa.heading') });
  const subheading = createElement('p', { className: 'login-form-subtitle', textContent: t('auth.cadastroEmpresa.subheading') });

  function goToLogin(event: Event): void {
    event.preventDefault();
    window.history.pushState({}, '', '/login');
    window.dispatchEvent(new PopStateEvent('popstate'));
  }

  if (!token) {
    const errorMsg = createElement('p', {
      className: 'login-error',
      textContent: t('auth.cadastroEmpresa.invalidToken')
    });
    const backLink = createElement('a', { className: 'login-forgot-link', textContent: t('auth.cadastroEmpresa.goToLogin') });
    backLink.href = '/login';
    backLink.addEventListener('click', goToLogin);

    const wrapper = createElement('div', { className: 'login-view' });
    wrapper.append(heading, subheading, errorMsg, backLink);
    card.appendChild(wrapper);
    formPanel.appendChild(card);
    page.appendChild(formPanel);
    return page;
  }

  const form = createElement('form', { className: 'login-form' });

  const nomeEmpresaField = createElement('label', { className: 'login-field' });
  const nomeEmpresaInputWrap = createElement('div', { className: 'login-field-input no-icon' });
  const nomeEmpresaInput = createElement('input');
  nomeEmpresaInput.type = 'text';
  nomeEmpresaInput.required = true;
  nomeEmpresaInputWrap.append(nomeEmpresaInput);
  nomeEmpresaField.append(createElement('span', { className: 'login-field-label', textContent: t('auth.cadastroEmpresa.nomeEmpresaLabel') }), nomeEmpresaInputWrap);

  const slugField = createElement('label', { className: 'login-field' });
  const slugInputWrap = createElement('div', { className: 'login-field-input no-icon' });
  const slugInput = createElement('input');
  slugInput.type = 'text';
  slugInput.required = true;
  slugInputWrap.append(slugInput);
  slugField.append(
    createElement('span', { className: 'login-field-label', textContent: t('auth.cadastroEmpresa.slugLabel') }),
    slugInputWrap,
    createElement('span', { className: 'login-hint', textContent: t('auth.cadastroEmpresa.slugHint') })
  );

  const senhaField = createElement('label', { className: 'login-field' });
  const senhaInputWrap = createElement('div', { className: 'login-field-input' });
  const senhaInput = createElement('input');
  senhaInput.type = 'password';
  senhaInput.placeholder = '••••••••••••';
  senhaInput.required = true;
  senhaInput.minLength = 6;
  senhaInput.autocomplete = 'new-password';
  senhaInputWrap.append(createIcon('lock', 'login-field-icon'), senhaInput);
  senhaField.append(createElement('span', { className: 'login-field-label', textContent: t('auth.cadastroEmpresa.senhaLabel') }), senhaInputWrap);

  const feedback = createElement('p', { className: 'login-error' });
  feedback.hidden = true;

  const submitButton = createElement('button', { className: 'login-submit-button button-with-icon', type: 'submit' });
  submitButton.append(createIcon('login'), document.createTextNode(t('auth.cadastroEmpresa.submit')));

  form.append(nomeEmpresaField, slugField, senhaField, feedback, submitButton);

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    feedback.hidden = true;
    submitButton.disabled = true;
    submitButton.classList.add('loading');

    try {
      await concluirCadastroPedidoPlano(token, nomeEmpresaInput.value.trim(), slugInput.value.trim(), senhaInput.value);
      const successMsg = createElement('p', {
        className: 'login-hint',
        textContent: t('auth.cadastroEmpresa.success')
      });
      const loginLink = createElement('a', { className: 'login-forgot-link', textContent: t('auth.cadastroEmpresa.goToLogin') });
      loginLink.href = '/login';
      loginLink.addEventListener('click', goToLogin);
      form.replaceChildren(successMsg, loginLink);
    } catch (error) {
      feedback.className = 'login-error';
      feedback.textContent = error instanceof Error ? error.message : t('auth.cadastroEmpresa.genericError');
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
