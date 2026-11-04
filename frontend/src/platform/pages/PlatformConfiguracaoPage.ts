import { createElement } from '../../dom';
import { createInput } from '../../components/formFields';
import { createStatusBadge } from '../../components/StatusBadge';
import { createUiState } from '../../components/UiState';
import { useGlobalLoading } from '../../hooks/useGlobalLoading';
import { useToast } from '../../hooks/useToast';
import { createPlatformLayout } from '../layouts/PlatformLayout';
import {
  getPlatformConfiguracao,
  updatePlatformConfiguracao,
  type PlatformConfiguracao,
  type PlatformConfiguracaoPayload
} from '../services/platformConfigService';
import { t } from '../../services/i18nService';

export function createPlatformConfiguracaoPage(): HTMLElement {
  const content = createElement('div', { className: 'content-stack' });
  const toast = useToast();
  const loading = useGlobalLoading();

  let config: PlatformConfiguracao | null = null;
  let failed = false;

  const render = (): void => {
    if (failed) {
      content.replaceChildren(createUiState({
        kind: 'error',
        title: t('platform.configuracao.loadError'),
        action: { label: t('platform.configuracao.retry'), onClick: load }
      }));
      return;
    }
    if (!config) {
      content.replaceChildren(createElement('p', { className: 'eyebrow', textContent: t('platform.configuracao.loading') }));
      return;
    }
    content.replaceChildren(createAsaasSection(config), createSignupSection(config));
  };

  const load = (): void => {
    failed = false;
    loading.show();
    void getPlatformConfiguracao()
      .then((data) => { config = data; render(); })
      .catch(() => { failed = true; render(); })
      .finally(() => loading.hide());
  };

  const applyUpdate = (payload: PlatformConfiguracaoPayload, onSuccess: () => void, onError: () => void = () => undefined): void => {
    loading.show();
    void updatePlatformConfiguracao(payload)
      .then((data) => {
        config = data;
        toast.success(t('platform.configuracao.savedSuccess'));
        onSuccess();
        render();
      })
      .catch((error) => {
        toast.error(error instanceof Error ? error.message : t('platform.configuracao.saveError'));
        onError();
      })
      .finally(() => loading.hide());
  };

  const createAsaasSection = (current: PlatformConfiguracao): HTMLElement => {
    const section = createElement('section', { className: 'data-panel' });
    section.appendChild(createElement('h2', { textContent: t('platform.configuracao.asaasTitle') }));
    section.appendChild(createElement('p', { className: 'eyebrow', textContent: t('platform.configuracao.asaasDescription') }));

    const form = createElement('form', { className: 'settings-form' });
    const baseUrl = createInput(t('platform.configuracao.fieldBaseUrl'), 'text', current.asaasApiBaseUrl ?? '');
    let baseUrlTouched = false;
    baseUrl.input.addEventListener('input', () => { baseUrlTouched = true; });

    const apiKey = createSecretField(
      t('platform.configuracao.fieldApiKey'),
      current.asaasApiKeyConfigurada,
      (onDone) => applyUpdate({ asaasApiKey: '' }, onDone)
    );
    const webhookToken = createSecretField(
      t('platform.configuracao.fieldWebhookToken'),
      current.asaasWebhookTokenConfigurada,
      (onDone) => applyUpdate({ asaasWebhookToken: '' }, onDone)
    );

    const save = createElement('button', { type: 'submit', textContent: t('platform.configuracao.saveButton') });
    const actions = createElement('div', { className: 'form-actions' });
    actions.appendChild(save);

    form.append(baseUrl.field, apiKey.field, webhookToken.field, actions);
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      const payload: PlatformConfiguracaoPayload = {};
      if (baseUrlTouched) payload.asaasApiBaseUrl = baseUrl.input.value.trim();
      if (apiKey.input.value.trim()) payload.asaasApiKey = apiKey.input.value.trim();
      if (webhookToken.input.value.trim()) payload.asaasWebhookToken = webhookToken.input.value.trim();
      if (Object.keys(payload).length === 0) { toast.warning(t('platform.configuracao.nothingToSave')); return; }
      save.disabled = true;
      applyUpdate(payload, () => undefined, () => { save.disabled = false; });
    });

    section.appendChild(form);
    return section;
  };

  const createSignupSection = (current: PlatformConfiguracao): HTMLElement => {
    const section = createElement('section', { className: 'data-panel' });
    section.appendChild(createElement('h2', { textContent: t('platform.configuracao.signupTitle') }));
    section.appendChild(createElement('p', { className: 'eyebrow', textContent: t('platform.configuracao.signupDescription') }));

    const form = createElement('form', { className: 'settings-form' });
    const code = createSecretField(
      t('platform.configuracao.fieldSignupCode'),
      current.signupCodeConfigurada,
      (onDone) => applyUpdate({ signupCode: '' }, onDone)
    );
    const empresaId = createInput(t('platform.configuracao.fieldSignupEmpresaId'), 'number', current.signupEmpresaId != null ? String(current.signupEmpresaId) : '');
    let empresaIdTouched = false;
    empresaId.input.addEventListener('input', () => { empresaIdTouched = true; });

    const save = createElement('button', { type: 'submit', textContent: t('platform.configuracao.saveButton') });
    const actions = createElement('div', { className: 'form-actions' });
    actions.appendChild(save);

    form.append(code.field, empresaId.field, actions);
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      const payload: PlatformConfiguracaoPayload = {};
      if (code.input.value.trim()) payload.signupCode = code.input.value.trim();
      if (empresaIdTouched) {
        const raw = empresaId.input.value.trim();
        payload.signupEmpresaId = raw === '' ? null : Number(raw);
      }
      if (Object.keys(payload).length === 0) { toast.warning(t('platform.configuracao.nothingToSave')); return; }
      save.disabled = true;
      applyUpdate(payload, () => undefined, () => { save.disabled = false; });
    });

    section.appendChild(form);
    return section;
  };

  const createSecretField = (
    label: string,
    configured: boolean,
    onRemove: (onDone: () => void) => void
  ): { field: HTMLElement; input: HTMLInputElement } => {
    const { field, input } = createInput(label, 'password', '');
    input.autocomplete = 'new-password';
    input.placeholder = configured ? t('platform.configuracao.configured') : t('platform.configuracao.notConfigured');
    const badge = createStatusBadge(
      configured ? t('platform.configuracao.configured') : t('platform.configuracao.notConfigured'),
      configured ? 'success' : 'warning'
    );
    field.appendChild(badge);
    if (configured) {
      const remove = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('platform.configuracao.removeButton') });
      remove.addEventListener('click', () => {
        remove.disabled = true;
        onRemove(() => { remove.disabled = false; });
      });
      field.appendChild(remove);
    }
    return { field, input };
  };

  load();

  return createPlatformLayout({
    content,
    title: t('platform.configuracao.title'),
    description: t('platform.configuracao.description')
  });
}
