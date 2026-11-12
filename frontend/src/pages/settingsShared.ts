import { createElement } from '../dom';
import { getCurrentUser } from '../services/authService';
import { type ApiCredentialProvider } from '../services/apiCredentialsService';
import { type BrandName } from '../components/BrandLogo';
import { t } from '../services/i18nService';

// ---------- Helpers compartilhados ----------

export function apiProviderOptions(): Array<{ value: ApiCredentialProvider; label: string; descricao: string; logo: BrandName }> {
  return [
    { value: 'resend', label: t('settings.integrations.resendLabel'), descricao: t('settings.integrations.resendDescricao'), logo: 'resend' },
    { value: 'asaas', label: t('settings.integrations.asaasLabel'), descricao: t('settings.integrations.asaasDescricao'), logo: 'asaas' },
    { value: 'piperun', label: t('settings.integrations.piperunLabel'), descricao: t('settings.integrations.piperunDescricao'), logo: 'piperun' }
  ];
}

export function asaasCredentialLabel(nome: string): string {
  const keys: Record<string, string> = {
    api_key_sandbox: 'settings.integrations.apiKeySandboxLabel',
    api_key_producao: 'settings.integrations.apiKeyProducaoLabel',
    webhook_token_sandbox: 'settings.integrations.webhookTokenSandboxLabel',
    webhook_token_producao: 'settings.integrations.webhookTokenProducaoLabel'
  };
  return (keys[nome] && t(keys[nome])) ?? nome;
}

export function credentialCopy(provider: ApiCredentialProvider, replacing = false, nome = ''): { label: string; hint: string; placeholder: string } {
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

export function createPanelHeader(eyebrowText: string, title: string, action?: HTMLElement): HTMLElement {
  const header = createElement('div', { className: 'panel-title' });
  const titleText = createElement('div');
  const eyebrow = createElement('span', { className: 'eyebrow', textContent: eyebrowText });
  const heading = createElement('h2', { textContent: title });

  titleText.append(eyebrow, heading);
  header.appendChild(titleText);
  if (action) header.appendChild(action);

  return header;
}

export function canManageSettings(): boolean {
  const role = getCurrentUser()?.role;
  return role === 'owner' || role === 'admin';
}

export function isPlatformAdmin(): boolean {
  return getCurrentUser()?.isPlatformAdmin === true;
}

export function createToggle(label: string, checked: boolean): { field: HTMLElement; checked: boolean } {
  const field = createElement('label', { className: 'form-field form-field-checkbox' });
  const input = createElement('input');
  input.type = 'checkbox';
  input.checked = checked;
  field.append(input, createElement('span', { textContent: label }));
  return { field, get checked() { return input.checked; }, set checked(value: boolean) { input.checked = value; } };
}
