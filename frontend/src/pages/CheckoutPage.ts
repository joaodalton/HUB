import { createElement } from '../dom';
import { createIcon } from '../components/Icon';
import { criarPedidoPlano } from '../services/pedidoPlanoService';
import { t } from '../services/i18nService';

type PlanoOption = { chave: 'starter' | 'avancado' | 'enterprise'; name: string; price: string; features: string };

// Catalogo publico de planos nao vem de API -- nao existe endpoint publico
// listando planos (ver backend/hub_platform/routes/platform_routes.py). As
// chaves precisam bater exatamente com o catalogo do backend
// (pedido_plano_service.py).
const PLANOS: PlanoOption[] = [
  { chave: 'starter', name: 'Starter', price: 'R$ 600/mês', features: '5 usinas, 300 UCs, 3 usuários' },
  { chave: 'avancado', name: 'Avançado', price: 'R$ 900/mês', features: '13 usinas, 750 UCs, 8 usuários, robô de leitura automática de faturas' },
  { chave: 'enterprise', name: 'Enterprise', price: 'R$ 1200/mês', features: '19 usinas, 1125 UCs, 12 usuários' }
];

type BillingTypeOption = { value: string; labelKey: string };

const BILLING_TYPES: BillingTypeOption[] = [
  { value: 'BOLETO', labelKey: 'auth.checkout.billingTypeBoleto' },
  { value: 'PIX', labelKey: 'auth.checkout.billingTypePix' },
  { value: 'CREDIT_CARD', labelKey: 'auth.checkout.billingTypeCreditCard' }
];

// Pagina publica de checkout -- sem sessao, chegada direta pela URL
// (/checkout). Mesma casca visual do ResetPasswordPage/ForgotPasswordPage.
export function createCheckoutPage(): HTMLElement {
  const page = createElement('section', { className: 'login-page' });
  page.style.gridTemplateColumns = '1fr';

  const formPanel = createElement('section', { className: 'login-form-panel' });
  const card = createElement('div', { className: 'login-form-card' });

  const heading = createElement('h1', { textContent: t('auth.checkout.heading') });
  const subheading = createElement('p', { className: 'login-form-subtitle', textContent: t('auth.checkout.subheading') });

  const form = createElement('form', { className: 'login-form' });

  const planField = createElement('div', { className: 'login-field' });
  planField.append(createElement('span', { className: 'login-field-label', textContent: t('auth.checkout.planLabel') }));
  const planOptions = createElement('div', { className: 'login-plan-options' });
  const planInputs: HTMLInputElement[] = [];
  PLANOS.forEach((plano) => {
    const option = createElement('label', { className: 'login-plan-option' });
    const input = createElement('input');
    input.type = 'radio';
    input.name = 'plano';
    input.value = plano.chave;
    const info = createElement('div', { className: 'login-plan-option-info' });
    info.append(
      createElement('span', { className: 'login-plan-option-name', textContent: plano.name }),
      createElement('span', { className: 'login-plan-option-price', textContent: plano.price }),
      createElement('span', { className: 'login-plan-option-features', textContent: plano.features })
    );
    option.append(input, info);
    input.addEventListener('change', () => {
      planInputs.forEach((otherInput) => otherInput.closest('.login-plan-option')?.classList.toggle('is-selected', otherInput.checked));
    });
    planInputs.push(input);
    planOptions.appendChild(option);
  });
  planField.appendChild(planOptions);

  const emailField = createElement('label', { className: 'login-field' });
  const emailInputWrap = createElement('div', { className: 'login-field-input' });
  const emailInput = createElement('input');
  emailInput.type = 'email';
  emailInput.placeholder = t('auth.login.emailPlaceholder');
  emailInput.required = true;
  emailInput.autocomplete = 'email';
  emailInputWrap.append(createIcon('user', 'login-field-icon'), emailInput);
  emailField.append(createElement('span', { className: 'login-field-label', textContent: t('auth.checkout.emailLabel') }), emailInputWrap);

  const nameField = createElement('label', { className: 'login-field' });
  const nameInputWrap = createElement('div', { className: 'login-field-input no-icon' });
  const nameInput = createElement('input');
  nameInput.type = 'text';
  nameInput.required = true;
  nameInput.autocomplete = 'name';
  nameInputWrap.append(nameInput);
  nameField.append(createElement('span', { className: 'login-field-label', textContent: t('auth.checkout.nameLabel') }), nameInputWrap);

  const cpfCnpjField = createElement('label', { className: 'login-field' });
  const cpfCnpjInputWrap = createElement('div', { className: 'login-field-input no-icon' });
  const cpfCnpjInput = createElement('input');
  cpfCnpjInput.type = 'text';
  cpfCnpjInput.required = true;
  cpfCnpjInputWrap.append(cpfCnpjInput);
  cpfCnpjField.append(createElement('span', { className: 'login-field-label', textContent: t('auth.checkout.cpfCnpjLabel') }), cpfCnpjInputWrap);

  const phoneField = createElement('label', { className: 'login-field' });
  const phoneInputWrap = createElement('div', { className: 'login-field-input no-icon' });
  const phoneInput = createElement('input');
  phoneInput.type = 'tel';
  phoneInput.autocomplete = 'tel';
  phoneInputWrap.append(phoneInput);
  phoneField.append(createElement('span', { className: 'login-field-label', textContent: t('auth.checkout.phoneLabel') }), phoneInputWrap);

  const billingField = createElement('div', { className: 'login-field' });
  billingField.append(createElement('span', { className: 'login-field-label', textContent: t('auth.checkout.billingTypeLabel') }));
  const billingOptions = createElement('div', { className: 'login-billing-options' });
  const billingInputs: HTMLInputElement[] = [];
  BILLING_TYPES.forEach((billingType) => {
    const option = createElement('label', { className: 'login-billing-option' });
    const input = createElement('input');
    input.type = 'radio';
    input.name = 'billingType';
    input.value = billingType.value;
    option.append(input, createElement('span', { textContent: t(billingType.labelKey) }));
    billingInputs.push(input);
    billingOptions.appendChild(option);
  });
  billingField.appendChild(billingOptions);

  const feedback = createElement('p', { className: 'login-error' });
  feedback.hidden = true;

  const submitButton = createElement('button', { className: 'login-submit-button button-with-icon', type: 'submit' });
  submitButton.append(createIcon('login'), document.createTextNode(t('auth.checkout.submit')));

  form.append(planField, emailField, nameField, cpfCnpjField, phoneField, billingField, feedback, submitButton);

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    feedback.hidden = true;

    const planoChave = planInputs.find((input) => input.checked)?.value ?? '';
    const billingType = billingInputs.find((input) => input.checked)?.value ?? '';
    const email = emailInput.value.trim();
    const name = nameInput.value.trim();
    const cpfCnpj = cpfCnpjInput.value.trim();

    if (!email || !name || !cpfCnpj || !planoChave || !billingType) {
      feedback.className = 'login-error';
      feedback.textContent = t('auth.checkout.missingFields');
      feedback.hidden = false;
      return;
    }

    submitButton.disabled = true;
    submitButton.classList.add('loading');

    try {
      await criarPedidoPlano(email, planoChave, {
        name,
        cpfCnpj,
        mobilePhone: phoneInput.value.trim() || undefined,
        billingType
      });
      const successMsg = createElement('p', { className: 'login-hint', textContent: t('auth.checkout.success') });
      form.replaceChildren(successMsg);
    } catch (error) {
      feedback.className = 'login-error';
      feedback.textContent = error instanceof Error ? error.message : t('auth.checkout.genericError');
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
