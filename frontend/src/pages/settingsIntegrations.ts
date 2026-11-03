import { createElement } from '../dom';
import { createInput, createSelectField } from '../components/formFields';
import { createIntegrationCard } from '../components/IntegrationCard';
import { type BrandName } from '../components/BrandLogo';
import { createModalShell } from '../components/Modal';
import { type ApiCredentialPayload, type ApiCredentialProvider, type ApiCredentialRow } from '../services/apiCredentialsService';
import { getGoogleAuthorizeUrl, type GoogleAccountRow } from '../services/googleAccountService';
import { type WhatsappIntegration, type WhatsappIntegrationInput } from '../services/whatsappService';
import { createPanelHeader, createToggle } from './settingsShared';
import { t } from '../services/i18nService';

// ---------- APIs e integrações ----------

function apiProviderOptions(): Array<{ value: ApiCredentialProvider; label: string; descricao: string; logo: BrandName }> {
  return [
    { value: 'resend', label: t('settings.integrations.resendLabel'), descricao: t('settings.integrations.resendDescricao'), logo: 'resend' },
    { value: 'asaas', label: t('settings.integrations.asaasLabel'), descricao: t('settings.integrations.asaasDescricao'), logo: 'asaas' }
  ];
}

function asaasCredentialLabel(nome: string): string {
  const keys: Record<string, string> = {
    api_key_sandbox: 'settings.integrations.apiKeySandboxLabel',
    api_key_producao: 'settings.integrations.apiKeyProducaoLabel',
    webhook_token_sandbox: 'settings.integrations.webhookTokenSandboxLabel',
    webhook_token_producao: 'settings.integrations.webhookTokenProducaoLabel'
  };
  return (keys[nome] && t(keys[nome])) ?? nome;
}

function credentialCopy(provider: ApiCredentialProvider, replacing = false, nome = ''): { label: string; hint: string; placeholder: string } {
  if (provider === 'asaas') {
    const isWebhook = nome.startsWith('webhook_token');
    return {
      label: replacing
        ? (isWebhook ? t('settings.integrations.newWebhookTokenOptional') : t('settings.integrations.newApiKeyOptional'))
        : (isWebhook ? t('settings.integrations.webhookTokenBaseLabel') : t('settings.integrations.apiKeyBaseLabel')),
      hint: isWebhook ? t('settings.integrations.webhookTokenHint') : t('settings.integrations.apiKeyHint'),
      placeholder: replacing ? t('settings.integrations.keepCurrentPlaceholder') : ''
    };
  }
  return {
    label: replacing ? t('settings.integrations.newSecretOptional') : t('settings.integrations.secretField'),
    hint: t('settings.integrations.secretSentOnlyHint'),
    placeholder: replacing ? t('settings.integrations.keepCurrentPlaceholder') : ''
  };
}

export function createApiCredentialsPanel(
  credentials: ApiCredentialRow[],
  loaded: boolean,
  loadError: boolean,
  canManage: boolean,
  onRetry: () => Promise<void>,
  onCreate: (data: Required<ApiCredentialPayload>) => Promise<void>,
  onUpdate: (id: number, data: Pick<ApiCredentialPayload, 'nome' | 'segredo'>) => Promise<void>,
  onTest: (credential: ApiCredentialRow) => Promise<void>,
  onDelete: (id: number) => Promise<void>,
  whatsapp: WhatsappIntegration | null,
  whatsappLoaded: boolean,
  onSaveWhatsapp: (input: WhatsappIntegrationInput) => Promise<void>,
  onTestWhatsapp: () => Promise<void>,
  onDeleteWhatsapp: () => Promise<void>,
  googleAccounts: GoogleAccountRow[],
  onActivateGoogleAccount: (id: number) => void,
  onDisconnectGoogleAccount: (id: number) => void
): HTMLElement {
  const panel = createElement('section', { className: 'settings-panel' });
  panel.appendChild(createPanelHeader(t('settings.integrations.heading'), t('settings.integrations.description')));

  if (!canManage) {
    panel.appendChild(createElement('p', { className: 'settings-hint', textContent: t('settings.integrations.denied') }));
    return panel;
  }

  if (!loaded) {
    panel.appendChild(createElement('p', { className: 'settings-hint', textContent: t('settings.integrations.loading') }));
    return panel;
  }

  if (loadError) {
    const message = createElement('p', { className: 'settings-hint', textContent: t('settings.integrations.loadError') });
    const retry = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('common.retry') });
    retry.addEventListener('click', () => void onRetry());
    panel.append(message, retry);
    return panel;
  }

  const grid = createElement('div', { className: 'integration-card-grid' });

  // O formulario so existe dentro do modal, aberto ao clicar no card. Salvar/remover fecham o modal
  // (a tela inteira e re-renderizada pelo estado); testar mantem aberto.
  const openModal = (title: string, build: (close: () => void) => HTMLElement[]): void => {
    const modal = createModalShell(title, t('settings.integrations.heading'));
    const content = createElement('div', { className: 'integration-modal-content' });
    content.append(...build(modal.close));
    modal.body.appendChild(content);
    document.body.appendChild(modal.overlay);
  };

  apiProviderOptions().forEach((provider) => {
    const providerCredentials = credentials.filter((credential) => credential.provider === provider.value);
    grid.appendChild(createIntegrationCard({
      nome: provider.label,
      descricao: provider.descricao,
      logo: provider.logo,
      status: providerCredentials.some((credential) => credential.configurada) ? 'conectado' : 'nao_configurado',
      onConfigurar: () => openModal(provider.label, (close) => {
        const create = async (data: Required<ApiCredentialPayload>) => { await onCreate(data); close(); };
        if (providerCredentials.length === 0) return [createApiCredentialForm(create, provider.value)];
        const cards = providerCredentials.map((credential) => {
          const card = createApiCredentialCard(
            credential,
            async (id, data) => { await onUpdate(id, data); close(); },
            onTest,
            async (id) => { await onDelete(id); close(); }
          ) as HTMLDetailsElement;
          card.open = true;
          return card;
        });
        const content = createElement('div', { className: 'integration-modal-content' });
        const add = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('settings.integrations.addAnother') });
        add.addEventListener('click', () => content.replaceChildren(createApiCredentialForm(create, provider.value)));
        content.append(...cards, add);
        return [content];
      })
    }));
  });
  grid.appendChild(createIntegrationCard({
    nome: t('settings.integrations.whatsappLabel'), descricao: t('settings.integrations.whatsappDescricao'), logo: 'whatsapp',
    status: whatsapp?.configured ? 'conectado' : 'nao_configurado',
    onConfigurar: () => openModal(t('settings.integrations.whatsappLabel'), (close) => [createWhatsappIntegrationForm(
      whatsapp,
      whatsappLoaded,
      async (input) => { await onSaveWhatsapp(input); close(); },
      onTestWhatsapp,
      async () => { await onDeleteWhatsapp(); close(); }
    )])
  }));
  grid.appendChild(createIntegrationCard({
    nome: t('settings.integrations.googleLabel'), descricao: t('settings.integrations.googleDescricao'), logo: 'google',
    status: googleAccounts.some((account) => account.ativa) ? 'conectado' : 'nao_configurado',
    onConfigurar: () => openModal(t('settings.integrations.googleLabel'), () => [createGoogleAccountsSection(googleAccounts, onActivateGoogleAccount, onDisconnectGoogleAccount)])
  }));
  panel.appendChild(grid);
  return panel;
}

// Contas Google conectadas via OAuth real (multiplas, com refresh token no banco).
function createGoogleAccountsSection(
  accounts: GoogleAccountRow[],
  onActivate: (id: number) => void,
  onDisconnect: (id: number) => void
): HTMLElement {
  const section = createElement('section', { className: 'database-provider-card' });
  const header = createElement('div', { className: 'provider-header' });
  const text = createElement('div');
  const eyebrow = createElement('span', { className: 'eyebrow', textContent: t('settings.integrations.googleAccountsEyebrow') });
  const heading = createElement('h2', { textContent: t('settings.integrations.googleAccountsHeading') });
  const connectLink = createElement('a', { className: 'small-button', textContent: t('settings.integrations.connectNewAccount') });

  connectLink.href = getGoogleAuthorizeUrl();

  text.append(eyebrow, heading);
  header.append(text, connectLink);
  section.appendChild(header);

  if (accounts.length === 0) {
    section.appendChild(createElement('p', {
      className: 'settings-hint',
      textContent: t('settings.integrations.noAccounts')
    }));
    return section;
  }

  const list = createElement('dl', { className: 'settings-list compact' });

  accounts.forEach((account) => {
    const label = createElement('dt', { textContent: account.email });
    const valueRow = createElement('dd', { className: 'account-row' });
    const status = createElement('span', {
      className: account.ativa ? 'provider-badge success' : 'provider-badge',
      textContent: account.ativa ? t('settings.integrations.active') : t('settings.integrations.inactive')
    });
    const activateButton = createElement('button', {
      className: 'secondary-button',
      textContent: t('settings.integrations.useThisAccount'),
      type: 'button'
    });
    const disconnectButton = createElement('button', {
      className: 'danger-button',
      textContent: t('settings.integrations.disconnect'),
      type: 'button'
    });

    activateButton.disabled = account.ativa;
    activateButton.addEventListener('click', () => onActivate(account.id));
    disconnectButton.addEventListener('click', () => {
      if (window.confirm(`${t('settings.integrations.disconnect')} ${account.email}?`)) onDisconnect(account.id);
    });

    valueRow.append(status, activateButton, disconnectButton);
    list.append(label, valueRow);
  });

  section.appendChild(list);
  return section;
}

function createWhatsappIntegrationForm(
  integration: WhatsappIntegration | null,
  loaded: boolean,
  onSave: (input: WhatsappIntegrationInput) => Promise<void>,
  onTest: () => Promise<void>,
  onDelete: () => Promise<void>
): HTMLElement {
  const form = createElement('form', { className: 'settings-form api-credential-form' });
  form.appendChild(createElement('p', { className: 'settings-hint', textContent: t('settings.integrations.whatsappTokenHint') }));
  if (!loaded) { form.appendChild(createElement('p', { className: 'settings-hint', textContent: t('settings.integrations.whatsappLoading') })); return form; }
  const phoneId = createInput(t('settings.integrations.phoneNumberId'), 'text', integration?.phoneNumberId ?? '', true);
  const wabaId = createInput(t('settings.integrations.wabaId'), 'text', integration?.businessAccountId ?? '', true);
  const display = createInput(t('settings.integrations.displayNumber'), 'text', integration?.displayPhoneNumber ?? '', false);
  const token = createInput(integration ? t('settings.integrations.newToken') : t('settings.integrations.token'), 'password', '', !integration);
  token.input.autocomplete = 'new-password';
  const enabled = createToggle(t('settings.integrations.enableIntegration'), integration?.enabled ?? true);
  const actions = createElement('div', { className: 'form-actions' });
  const save = createElement('button', { type: 'submit', textContent: t('settings.integrations.saveWhatsapp') });
  actions.appendChild(save);
  if (integration) {
    const test = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('settings.integrations.testConnection') });
    test.addEventListener('click', () => void onTest());
    const remove = createElement('button', { className: 'danger-button', type: 'button', textContent: t('settings.integrations.disconnect') });
    remove.addEventListener('click', () => void onDelete());
    actions.append(test, remove);
  }
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const input: WhatsappIntegrationInput = { phoneNumberId: phoneId.input.value.trim(), businessAccountId: wabaId.input.value.trim(), displayPhoneNumber: display.input.value.trim(), enabled: enabled.checked };
    if (token.input.value.trim()) input.accessToken = token.input.value.trim();
    void onSave(input);
  });
  form.append(phoneId.field, wabaId.field, display.field, token.field, enabled.field, actions);
  return form;
}

function createApiCredentialCard(
  credential: ApiCredentialRow,
  onUpdate: (id: number, data: Pick<ApiCredentialPayload, 'nome' | 'segredo'>) => Promise<void>,
  onTest: (credential: ApiCredentialRow) => Promise<void>,
  onDelete: (id: number) => Promise<void>
): HTMLElement {
  const card = createElement('details', { className: 'api-credential-card' });
  const summary = createElement('summary', { className: 'api-credential-summary' });
  const provider = apiProviderOptions().find((option) => option.value === credential.provider)?.label ?? credential.provider;
  const status = createElement('span', { className: credential.configurada ? 'provider-badge success' : 'provider-badge warning', textContent: credential.configurada ? t('settings.integrations.configured') : t('settings.integrations.noSecret') });
  const title = createElement('div', { className: 'api-credential-title' });
  title.append(createElement('strong', { textContent: credential.provider === 'asaas' ? asaasCredentialLabel(credential.nome) : credential.nome }), createElement('span', { textContent: provider }));
  summary.append(title, status);

  const body = createElement('form', { className: 'settings-form api-credential-form' });
  const providerField = createElement('label', { className: 'form-field' });
  providerField.append(
    createElement('span', { textContent: t('settings.integrations.provider') }),
    createElement('strong', { textContent: provider })
  );
  const nameField = createInput(t('settings.integrations.integrationName'), 'text', credential.nome, true);
  const copy = credentialCopy(credential.provider, true, credential.nome);
  const secretField = createInput(copy.label, 'password', '', false);
  secretField.input.autocomplete = 'new-password';
  secretField.input.placeholder = copy.placeholder;
  const hint = createElement('p', { className: 'settings-hint', textContent: `${copy.hint} ${t('settings.integrations.secretNotRetrievableSuffix')}` });
  if (credential.provider === 'asaas') {
    nameField.input.readOnly = true;
    nameField.field.appendChild(createElement('small', { className: 'settings-hint', textContent: t('settings.integrations.asaasFixedIdHint') }));
  }
  const actions = createElement('div', { className: 'form-actions' });
  const save = createElement('button', { type: 'submit', textContent: t('settings.integrations.saveChanges') });
  const test = credential.provider === 'asaas' ? createElement('button', { className: 'secondary-button', type: 'button', textContent: credential.nome.startsWith('webhook_token') ? t('settings.integrations.verifyLocalCipher') : t('settings.integrations.testApiKey') }) : null;
  const remove = createElement('button', { className: 'danger-button', type: 'button', textContent: t('common.remove') });
  body.addEventListener('submit', async (event) => {
    event.preventDefault();
    const nome = nameField.input.value.trim();
    if (!nome) { nameField.input.focus(); return; }
    save.disabled = true;
    save.textContent = t('common.saving');
    try {
      const segredo = secretField.input.value;
      await onUpdate(credential.id, { nome, ...(segredo ? { segredo } : {}) });
    } catch {
      save.disabled = false;
      save.textContent = t('settings.integrations.saveChanges');
    }
  });
  if (test) test.addEventListener('click', () => void onTest(credential));
  remove.addEventListener('click', async () => {
    if (!window.confirm(`${t('common.remove')}: "${credential.nome}"?`)) return;
    remove.disabled = true;
    await onDelete(credential.id);
    remove.disabled = false;
  });
  actions.append(save, ...(test ? [test] : []), remove);
  body.append(providerField, nameField.field, secretField.field, hint, actions);
  card.append(summary, body);
  return card;
}

function createApiCredentialForm(onCreate: (data: Required<ApiCredentialPayload>) => Promise<void>, provider: ApiCredentialProvider): HTMLElement {
  const form = createElement('form', { className: 'settings-form api-credential-form' });
  form.appendChild(createElement('h3', { textContent: t('settings.integrations.addIntegration') }));
  const nameField = createInput(t('settings.integrations.integrationName'), 'text', '', true);
  const asaasType = createSelectField(t('settings.integrations.asaasCredentialType'), 'api_key', [
    { value: 'api_key', label: t('settings.integrations.asaasApiKeyOption') },
    { value: 'webhook_token', label: t('settings.integrations.asaasWebhookOption') }
  ]);
  const asaasEnvironment = createSelectField(t('settings.integrations.asaasEnvironment'), 'sandbox', [
    { value: 'sandbox', label: t('settings.integrations.sandbox') },
    { value: 'producao', label: t('settings.integrations.producao') }
  ]);
  const secretField = createInput(t('settings.integrations.secretField'), 'password', '', true);
  secretField.input.autocomplete = 'new-password';
  const hint = createElement('p', { className: 'settings-hint' });
  const webhookHint = createElement('p', { className: 'settings-hint api-webhook-hint', textContent: t('settings.integrations.webhookEnvHint') });
  const isAsaas = provider === 'asaas';
  function refreshProviderCopy(): void {
    const nome = `${asaasType.select.value}_${asaasEnvironment.select.value}`;
    const copy = credentialCopy(provider, false, nome);
    secretField.field.firstElementChild!.textContent = copy.label;
    secretField.input.placeholder = copy.placeholder;
    hint.textContent = copy.hint;
  }
  nameField.field.hidden = isAsaas;
  nameField.input.required = !isAsaas;
  asaasType.field.hidden = !isAsaas;
  asaasEnvironment.field.hidden = !isAsaas;
  webhookHint.hidden = !isAsaas;
  asaasType.select.addEventListener('change', refreshProviderCopy);
  asaasEnvironment.select.addEventListener('change', refreshProviderCopy);
  refreshProviderCopy();
  const actions = createElement('div', { className: 'form-actions' });
  const submit = createElement('button', { type: 'submit', textContent: t('settings.integrations.add') });
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const nome = isAsaas
      ? `${asaasType.select.value}_${asaasEnvironment.select.value}`
      : nameField.input.value.trim();
    const segredo = secretField.input.value;
    if (!nome) { nameField.input.focus(); return; }
    if (!segredo) { secretField.input.focus(); return; }
    submit.disabled = true;
    submit.textContent = t('settings.integrations.adding');
    try {
      await onCreate({ provider, nome, segredo });
    } catch {
      submit.disabled = false;
      submit.textContent = t('settings.integrations.add');
    }
  });
  actions.appendChild(submit);
  form.append(nameField.field, asaasType.field, asaasEnvironment.field, secretField.field, hint, webhookHint, actions);
  return form;
}
