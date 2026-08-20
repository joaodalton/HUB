import { createElement } from '../dom';
import { createIcon } from '../components/Icon';
import { HUB_VERSION } from '../components/Sidebar';
import { config } from '../services/config';
import { login } from '../services/authService';

// Sem auto-cadastro publico (decisao 2026-08-19) -- todo acesso nasce de
// convite (Invitation/aceitar-convite), inclusive pra empresa nova (ver
// scripts/criar_empresa.py). Tela de login so mostra o formulario de login,
// sem alternador de modo nem botao "Criar uma conta".
export function createLoginPage(onSuccess: () => void): HTMLElement {
  const page = createElement('section', { className: 'login-page' });

  const formPanel = createElement('section', { className: 'login-form-panel' });
  const card = createElement('div', { className: 'login-form-card' });

  function render(): void {
    card.replaceChildren(createLoginView());
  }

  function createLoginView(): HTMLElement {
    const heading = createElement('h1', { textContent: 'Bem-vindo ao HUB' });
    const subheading = createElement('p', { className: 'login-form-subtitle', textContent: 'Faça login para continuar' });

    const form = createElement('form', { className: 'login-form' });
    const emailField = createLoginField('E-mail', 'email', 'usuario@email.com', 'user');
    const senhaField = createLoginField('Senha', 'password', '••••••••••••', 'lock', true);

    const rememberRow = createElement('label', { className: 'login-checkbox-row' });
    const rememberInput = createElement('input');
    rememberInput.type = 'checkbox';
    rememberRow.append(rememberInput, createElement('span', { textContent: 'Lembrar meu acesso' }));

    const errorText = createElement('p', { className: 'login-error' });
    errorText.hidden = true;

    const submitButton = createElement('button', { className: 'login-submit-button button-with-icon', type: 'submit' });
    submitButton.append(createIcon('login'), document.createTextNode('Entrar no HUB'));

    form.append(emailField.field, senhaField.field, rememberRow, errorText, submitButton);

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      errorText.hidden = true;
      submitButton.disabled = true;
      submitButton.classList.add('loading');

      try {
        await login(emailField.input.value.trim(), senhaField.input.value, rememberInput.checked);
        onSuccess();
      } catch (error) {
        errorText.textContent = error instanceof Error ? error.message : 'Não foi possível entrar.';
        errorText.hidden = false;
      } finally {
        submitButton.disabled = false;
        submitButton.classList.remove('loading');
      }
    });

    const forgotLink = createElement('a', { className: 'login-forgot-link', textContent: 'Esqueci minha senha' });
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

  const brand = createElement('div', { className: 'login-illustration-brand' });
  const mark = createElement('span', { className: 'login-illustration-mark' });
  const brandText = createElement('span', { className: 'login-illustration-title', textContent: 'HUB' });
  brand.append(mark, brandText);

  const subtitle = createElement('p', { className: 'login-illustration-subtitle', textContent: 'Sistema de Gestão' });

  const art = createElement('div', { className: 'login-illustration-art' });
  art.innerHTML = loginArtMarkup();

  const tagline = createElement('p', {
    className: 'login-illustration-tagline',
    textContent: 'Conectando usinas, unidades e pessoas.'
  });

  panel.append(brand, subtitle, art, tagline);
  return panel;
}

// Nao e a arte 3D isometrica renderizada do mockup (aquilo e trabalho de
// design/3D, sem como reproduzir o mesmo acabamento em SVG feito a mao) --
// mas usa os mesmos elementos (usina central, painel solar, predio, casas,
// pinos de localizacao, linhas conectando tudo) como icones de linha simples.
function loginArtMarkup(): string {
  return `<svg viewBox="0 0 320 220" fill="none" xmlns="http://www.w3.org/2000/svg">
    <!-- linhas de conexao -->
    <g stroke-width="1.5" fill="none">
      <path d="M95 150 L150 120" stroke="#5b8def" opacity="0.5"/>
      <path d="M150 120 L205 100" stroke="var(--accent)" opacity="0.6"/>
      <path d="M205 100 L260 130" stroke="#5b8def" opacity="0.5"/>
      <path d="M205 100 L205 60" stroke="#5b8def" opacity="0.4"/>
      <path d="M150 120 L150 165" stroke="#5b8def" opacity="0.4"/>
      <path d="M260 130 L260 170" stroke="#5b8def" opacity="0.4"/>
    </g>

    <!-- usina (centro, laranja) -->
    <g transform="translate(150 120)">
      <circle r="16" fill="var(--accent)" opacity="0.12"/>
      <rect x="-9" y="-8" width="18" height="14" rx="1.5" stroke="var(--accent)" stroke-width="1.6"/>
      <path d="M-1.5 -5 L-4.5 1 L-0.5 1 L-3 5.5" stroke="var(--accent)" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
    </g>

    <!-- painel solar (esquerda) -->
    <g transform="translate(95 150)">
      <circle r="13" fill="#5b8def" opacity="0.1"/>
      <g stroke="#5b8def" stroke-width="1.3">
        <rect x="-9" y="-6" width="18" height="12" rx="1"/>
        <path d="M-9 -2 H9 M-9 2 H9 M-3 -6 V6 M3 -6 V6"/>
      </g>
    </g>

    <!-- predio (direita) -->
    <g transform="translate(260 130)">
      <circle r="13" fill="#5b8def" opacity="0.1"/>
      <rect x="-6" y="-9" width="12" height="18" rx="1" stroke="#5b8def" stroke-width="1.3"/>
      <path d="M-3 -5 h2 M1 -5 h2 M-3 -1 h2 M1 -1 h2 M-3 3 h2 M1 3 h2" stroke="#5b8def" stroke-width="1.1" stroke-linecap="round"/>
    </g>

    <!-- casas (nos dois pinos de cima) -->
    <g transform="translate(205 100)">
      <circle r="13" fill="var(--accent)" opacity="0.1"/>
      <path d="M-7 2 V-2 L0 -8 L7 -2 V2 Z" stroke="var(--accent)" stroke-width="1.3" stroke-linejoin="round"/>
      <path d="M-2 2 V-1 h4 v3" stroke="var(--accent)" stroke-width="1.1"/>
    </g>
    <g transform="translate(205 55)">
      <circle r="11" fill="#5b8def" opacity="0.1"/>
      <path d="M-6 2 V-1 L0 -6 L6 -1 V2 Z" stroke="#5b8def" stroke-width="1.2" stroke-linejoin="round"/>
    </g>
    <g transform="translate(150 170)">
      <circle r="11" fill="#5b8def" opacity="0.1"/>
      <path d="M-6 2 V-1 L0 -6 L6 -1 V2 Z" stroke="#5b8def" stroke-width="1.2" stroke-linejoin="round"/>
    </g>
    <g transform="translate(260 175)">
      <circle r="11" fill="#5b8def" opacity="0.1"/>
      <path d="M-6 2 V-1 L0 -6 L6 -1 V2 Z" stroke="#5b8def" stroke-width="1.2" stroke-linejoin="round"/>
    </g>

    <!-- pontos de rede soltos, mesmo espirito da versao anterior -->
    <circle cx="45" cy="185" r="3" fill="#5b8def" opacity="0.5"/>
    <circle cx="290" cy="60" r="3" fill="var(--accent)" opacity="0.5"/>
  </svg>`;
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
    toggle.setAttribute('aria-label', 'Mostrar senha');

    toggle.addEventListener('click', () => {
      const isHidden = input.type === 'password';
      input.type = isHidden ? 'text' : 'password';
      toggle.setAttribute('aria-label', isHidden ? 'Ocultar senha' : 'Mostrar senha');
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
  const label = createElement('span', { textContent: 'Verificando servidor...' });

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
      label.textContent = 'Servidor Online';
    })
    .catch(() => {
      dot.classList.add('offline');
      label.textContent = 'Servidor Offline';
    });

  return footer;
}