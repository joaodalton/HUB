import { createElement } from '../dom';
import { createInput, createSelectField } from '../components/formFields';
import { type ApiCredentialPayload, type ApiCredentialProvider, type ApiCredentialRow } from '../services/apiCredentialsService';
import { apiProviderOptions, asaasCredentialLabel, credentialCopy } from './settingsShared';
import { t } from '../services/i18nService';

export function createApiCredentialCard(
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

export function createApiCredentialForm(onCreate: (data: Required<ApiCredentialPayload>) => Promise<void>, provider: ApiCredentialProvider): HTMLElement {
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
