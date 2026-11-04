import { createElement } from '../dom';
import { createIcon } from '../components/Icon';
import { createLogoMark } from '../components/LogoMark';
import { HUB_VERSION } from '../components/Sidebar';
import { config } from '../services/config';
import { login, type AuthUser } from '../services/authService';
import { t } from '../services/i18nService';

// Sem auto-cadastro publico (decisao 2026-08-19) -- todo acesso nasce de
// convite (Invitation/aceitar-convite), inclusive pra empresa nova (ver
// scripts/criar_empresa.py). Tela de login so mostra o formulario de login,
// sem alternador de modo nem botao "Criar uma conta".
export function createLoginPage(onSuccess: (user: AuthUser) => void): HTMLElement {
  const page = createElement('section', { className: 'login-page' });

  const formPanel = createElement('section', { className: 'login-form-panel' });
  const card = createElement('div', { className: 'login-form-card' });

  function render(): void {
    card.replaceChildren(createLoginView());
  }

  function createLoginView(): HTMLElement {
    const heading = createElement('h1', { textContent: t('auth.login.heading') });
    const subheading = createElement('p', { className: 'login-form-subtitle', textContent: t('auth.login.subheading') });

    const form = createElement('form', { className: 'login-form' });
    const emailField = createLoginField(t('auth.login.emailLabel'), 'email', t('auth.login.emailPlaceholder'), 'user');
    const senhaField = createLoginField(t('auth.login.senhaLabel'), 'password', '••••••••••••', 'lock', true);

    const rememberRow = createElement('label', { className: 'login-checkbox-row' });
    const rememberInput = createElement('input');
    rememberInput.type = 'checkbox';
    rememberRow.append(rememberInput, createElement('span', { textContent: t('auth.login.rememberMe') }));

    const errorText = createElement('p', { className: 'login-error' });
    errorText.hidden = true;

    const submitButton = createElement('button', { className: 'login-submit-button button-with-icon', type: 'submit' });
    submitButton.append(createIcon('login'), document.createTextNode(t('auth.login.submit')));

    form.append(emailField.field, senhaField.field, rememberRow, errorText, submitButton);

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      errorText.hidden = true;
      submitButton.disabled = true;
      submitButton.classList.add('loading');

      try {
        const user = await login(emailField.input.value.trim(), senhaField.input.value, rememberInput.checked);
        onSuccess(user);
      } catch (error) {
        errorText.textContent = error instanceof Error ? error.message : t('auth.login.genericError');
        errorText.hidden = false;
      } finally {
        submitButton.disabled = false;
        submitButton.classList.remove('loading');
      }
    });

    const forgotLink = createElement('a', { className: 'login-forgot-link', textContent: t('auth.login.forgotPassword') });
    forgotLink.href = '/esqueci-senha';
    forgotLink.addEventListener('click', (event) => {
      event.preventDefault();
      window.history.pushState({}, '', '/esqueci-senha');
      window.dispatchEvent(new PopStateEvent('popstate'));
    });

    const wrapper = createElement('div', { className: 'login-view' });
    wrapper.append(heading, subheading, form, forgotLink, createLoginStatusFooter());
    return wrapper;
  }

  render();
  formPanel.appendChild(card);
  page.append(createLoginIllustration(), formPanel);

  return page;
}

// Nao e a arte isometrica 3D do mockup (isso e trabalho de design, nao da
// pra recriar com o mesmo acabamento via CSS/SVG) -- mantem a mesma ideia
// (rede conectada, cores da marca) de um jeito leve e reaproveitavel.
function createLoginIllustration(): HTMLElement {
  const panel = createElement('aside', { className: 'login-illustration' });

  const background = createElement('img', { className: 'login-illustration-video' }) as HTMLImageElement;
  const LOGIN_BACKGROUNDS = [
    '/media/login-background.gif',
    '/media/login-background-2.gif',
    '/media/login-background-4.gif'
  ];
  background.src = LOGIN_BACKGROUNDS[Math.floor(Math.random() * LOGIN_BACKGROUNDS.length)];
  background.alt = '';
  background.setAttribute('aria-hidden', 'true');
  background.addEventListener('error', () => background.classList.add('is-hidden'));

  const brand = createElement('div', { className: 'login-illustration-brand' });
  const mark = createLogoMark('login-illustration-mark');
  const brandText = createElement('span', { className: 'login-illustration-title', textContent: 'HUB' });
  brand.append(mark, brandText);

  const subtitle = createElement('p', { className: 'login-illustration-subtitle', textContent: t('auth.login.subtitle') });

  const header = createElement('div', { className: 'login-illustration-header' });
  header.append(brand, subtitle);

  const tagline = createElement('p', {
    className: 'login-illustration-tagline',
    textContent: t('auth.login.tagline')
  });

  panel.append(background, header, tagline);
  return panel;
}

function createLoginField(
  label: string,
  type: string,
  placeholder: string,
  icon?: 'user' | 'lock',
  isPassword = false
): { field: HTMLElement; input: HTMLInputElement } {
  const field = createElement('label', { className: 'login-field' });
  const labelText = createElement('span', { className: 'login-field-label', textContent: label });
  const inputWrap = createElement('div', { className: icon ? 'login-field-input' : 'login-field-input no-icon' });
  const input = createElement('input');

  input.type = type;
  input.placeholder = placeholder;
  input.required = true;
  input.autocomplete = type === 'password' ? 'current-password' : type === 'email' ? 'email' : 'off';

  if (icon) inputWrap.appendChild(createIcon(icon, 'login-field-icon'));
  inputWrap.appendChild(input);

  if (isPassword) {
    const toggle = createElement('button', { className: 'login-field-toggle', type: 'button' });
    toggle.appendChild(createIcon('eye'));
    toggle.setAttribute('aria-label', t('auth.login.showPassword'));

    toggle.addEventListener('click', () => {
      const isHidden = input.type === 'password';
      input.type = isHidden ? 'text' : 'password';
      toggle.setAttribute('aria-label', isHidden ? t('auth.login.hidePassword') : t('auth.login.showPassword'));
    });

    inputWrap.appendChild(toggle);
  }

  field.append(labelText, inputWrap);
  return { field, input };
}

function createLoginStatusFooter(): HTMLElement {
  const footer = createElement('div', { className: 'login-status-footer' });
  const statusText = createElement('span', { className: 'login-status-text' });
  const dot = createElement('span', { className: 'login-status-dot' });
  const label = createElement('span', { textContent: t('auth.login.checkingServer') });

  statusText.append(dot, label);
  const version = createElement('span', { className: 'login-status-version', textContent: `HUB ${HUB_VERSION}` });

  footer.append(statusText, version);

  // Ping no health check publico (GET /, sem prefixo /api/v1 -- ver
  // health_routes.py) -- nao usa apiRequest() porque essa rota nao vive
  // sob config.apiPrefix.
  fetch(config.apiBaseUrl)
    .then((response) => {
      if (!response.ok) throw new Error();
      dot.classList.add('online');
      label.textContent = t('auth.login.serverOnline');
    })
    .catch(() => {
      dot.classList.add('offline');
      label.textContent = t('auth.login.serverOffline');
    });

  return footer;
}
