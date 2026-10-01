import { createElement } from '../dom';
import { createInput, createSelectField } from '../components/formFields';
import { createIntegrationCard } from '../components/IntegrationCard';
import type { IconName } from '../components/Icon';
import { type ApiCredentialPayload, type ApiCredentialProvider, type ApiCredentialRow } from '../services/apiCredentialsService';
import { type WhatsappIntegration, type WhatsappIntegrationInput } from '../services/whatsappService';
import { createPanelHeader, createToggle } from './settingsShared';

// ---------- APIs e integrações ----------

const API_PROVIDER_OPTIONS: Array<{ value: ApiCredentialProvider; label: string; descricao: string; icon: IconName }> = [
  { value: 'resend', label: 'Resend (e-mail)', descricao: 'Envio de e-mails transacionais.', icon: 'mensagens' },
  { value: 'asaas', label: 'Asaas (financeiro)', descricao: 'Cobranças e faturas da empresa.', icon: 'cobrancas' },
  { value: 'concessionaria', label: 'Concessionária', descricao: 'Credenciais de serviços das concessionárias.', icon: 'plants' }
];

function asaasCredentialLabel(nome: string): string {
  const labels: Record<string, string> = {
    api_key_sandbox: 'Chave de API — Sandbox',
    api_key_producao: 'Chave de API — Produção',
    webhook_token_sandbox: 'Token do webhook — Sandbox',
    webhook_token_producao: 'Token do webhook — Produção'
  };
  return labels[nome] ?? nome;
}

function credentialCopy(provider: ApiCredentialProvider, replacing = false, nome = ''): { label: string; hint: string; placeholder: string } {
  if (provider === 'asaas') return {
    label: `${replacing ? 'Novo ' : ''}${nome.startsWith('webhook_token') ? 'token do webhook' : 'chave de API'}${replacing ? ' (opcional)' : ''}`,
    hint: nome.startsWith('webhook_token')
      ? 'Token de autenticação configurado no webhook do Asaas. O Asaas envia esse valor no header asaas-access-token; não use a chave de API aqui.'
      : 'Chave de API da conta Asaas usada pelo HUB para criar e consultar cobranças. Não use o token do webhook aqui.',
    placeholder: replacing ? 'Deixe em branco para manter o atual' : ''
  };
  return {
    label: replacing ? 'Novo segredo (opcional)' : 'Segredo de acesso',
    hint: 'O segredo é enviado apenas para ser protegido no servidor; ele não será listado, preenchido novamente nem gravado pelo navegador.',
    placeholder: replacing ? 'Deixe em branco para manter o atual' : ''
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
  onDeleteWhatsapp: () => Promise<void>
): HTMLElement {
  const panel = createElement('section', { className: 'settings-panel' });
  panel.appendChild(createPanelHeader('APIs e Integrações', 'Credenciais por empresa para serviços externos. O segredo nunca é exibido depois de salvo.'));

  if (!canManage) {
    panel.appendChild(createElement('p', { className: 'settings-hint', textContent: 'Seu perfil não tem permissão para visualizar ou administrar credenciais de integração.' }));
    return panel;
  }

  if (!loaded) {
    panel.appendChild(createElement('p', { className: 'settings-hint', textContent: 'Carregando integrações...' }));
    return panel;
  }

  if (loadError) {
    const message = createElement('p', { className: 'settings-hint', textContent: 'Não foi possível carregar as integrações.' });
    const retry = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Tentar novamente' });
    retry.addEventListener('click', () => void onRetry());
    panel.append(message, retry);
    return panel;
  }

  const grid = createElement('div', { className: 'integration-card-grid' });
  const editor = createElement('div', { className: 'integration-editor' });
  editor.appendChild(createElement('p', { className: 'settings-hint', textContent: 'Selecione uma integração para configurar suas credenciais.' }));

  API_PROVIDER_OPTIONS.forEach((provider) => {
    const providerCredentials = credentials.filter((credential) => credential.provider === provider.value);
    grid.appendChild(createIntegrationCard({
      nome: provider.label,
      descricao: provider.descricao,
      icon: provider.icon,
      status: providerCredentials.some((credential) => credential.configurada) ? 'conectado' : 'nao_configurado',
      onConfigurar: () => {
        if (providerCredentials.length === 0) {
          editor.replaceChildren(createApiCredentialForm(onCreate, provider.value));
          return;
        }
        const cards = providerCredentials.map((credential) => {
          const card = createApiCredentialCard(credential, onUpdate, onTest, onDelete) as HTMLDetailsElement;
          card.open = true;
          return card;
        });
        const add = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Adicionar outra credencial' });
        add.addEventListener('click', () => editor.replaceChildren(createApiCredentialForm(onCreate, provider.value)));
        editor.replaceChildren(...cards, add);
      }
    }));
  });
  grid.appendChild(createIntegrationCard({
    nome: 'WhatsApp Meta Cloud API', descricao: 'Número, token permanente e aprovação de templates por empresa.', icon: 'mensagens',
    status: whatsapp?.configured ? 'conectado' : 'nao_configurado',
    onConfigurar: () => editor.replaceChildren(createWhatsappIntegrationForm(whatsapp, whatsappLoaded, onSaveWhatsapp, onTestWhatsapp, onDeleteWhatsapp))
  }));
  panel.append(grid, editor);
  return panel;
}

function createWhatsappIntegrationForm(
  integration: WhatsappIntegration | null,
  loaded: boolean,
  onSave: (input: WhatsappIntegrationInput) => Promise<void>,
  onTest: () => Promise<void>,
  onDelete: () => Promise<void>
): HTMLElement {
  const form = createElement('form', { className: 'settings-form api-credential-form' });
  form.appendChild(createElement('p', { className: 'settings-hint', textContent: 'Use o token permanente do usuário de sistema da Meta. Ele é cifrado e nunca volta para esta tela.' }));
  if (!loaded) { form.appendChild(createElement('p', { className: 'settings-hint', textContent: 'Carregando configuração WhatsApp...' })); return form; }
  const phoneId = createInput('Phone Number ID', 'text', integration?.phoneNumberId ?? '', true);
  const wabaId = createInput('WhatsApp Business Account ID', 'text', integration?.businessAccountId ?? '', true);
  const display = createInput('Número exibido (opcional)', 'text', integration?.displayPhoneNumber ?? '', false);
  const token = createInput(integration ? 'Novo token permanente (opcional)' : 'Token permanente', 'password', '', !integration);
  token.input.autocomplete = 'new-password';
  const enabled = createToggle('Ativar integração para esta empresa', integration?.enabled ?? true);
  const actions = createElement('div', { className: 'form-actions' });
  const save = createElement('button', { type: 'submit', textContent: 'Salvar WhatsApp' });
  actions.appendChild(save);
  if (integration) {
    const test = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Testar conexão' });
    test.addEventListener('click', () => void onTest());
    const remove = createElement('button', { className: 'danger-button', type: 'button', textContent: 'Desconectar' });
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
  const provider = API_PROVIDER_OPTIONS.find((option) => option.value === credential.provider)?.label ?? credential.provider;
  const status = createElement('span', { className: credential.configurada ? 'provider-badge success' : 'provider-badge warning', textContent: credential.configurada ? 'Configurada' : 'Sem segredo' });
  const title = createElement('div', { className: 'api-credential-title' });
  title.append(createElement('strong', { textContent: credential.provider === 'asaas' ? asaasCredentialLabel(credential.nome) : credential.nome }), createElement('span', { textContent: provider }));
  summary.append(title, status);

  const body = createElement('form', { className: 'settings-form api-credential-form' });
  const providerField = createElement('label', { className: 'form-field' });
  providerField.append(
    createElement('span', { textContent: 'Provedor' }),
    createElement('strong', { textContent: provider })
  );
  const nameField = createInput('Nome da integração', 'text', credential.nome, true);
  const copy = credentialCopy(credential.provider, true, credential.nome);
  const secretField = createInput(copy.label, 'password', '', false);
  secretField.input.autocomplete = 'new-password';
  secretField.input.placeholder = copy.placeholder;
  const hint = createElement('p', { className: 'settings-hint', textContent: `${copy.hint} Por segurança, o valor atual não pode ser consultado ou exibido.` });
  if (credential.provider === 'asaas') {
    nameField.input.readOnly = true;
    nameField.field.appendChild(createElement('small', { className: 'settings-hint', textContent: 'Identificador técnico fixo: alterar o nome impediria o HUB de localizar esta credencial.' }));
  }
  const actions = createElement('div', { className: 'form-actions' });
  const save = createElement('button', { type: 'submit', textContent: 'Salvar alterações' });
  const test = credential.provider === 'asaas' ? createElement('button', { className: 'secondary-button', type: 'button', textContent: credential.nome.startsWith('webhook_token') ? 'Verificar cifra local' : 'Testar chave API' }) : null;
  const remove = createElement('button', { className: 'danger-button', type: 'button', textContent: 'Remover' });
  body.addEventListener('submit', async (event) => {
    event.preventDefault();
    const nome = nameField.input.value.trim();
    if (!nome) { nameField.input.focus(); return; }
    save.disabled = true;
    save.textContent = 'Salvando...';
    try {
      const segredo = secretField.input.value;
      await onUpdate(credential.id, { nome, ...(segredo ? { segredo } : {}) });
    } catch {
      save.disabled = false;
      save.textContent = 'Salvar alterações';
    }
  });
  if (test) test.addEventListener('click', () => void onTest(credential));
  remove.addEventListener('click', async () => {
    if (!window.confirm(`Remover a integração "${credential.nome}"?`)) return;
    remove.disabled = true;
    await onDelete(credential.id);
    remove.disabled = false;
  });
  actions.append(save, ...(test ? [test] : []), remove);
  body.append(providerField, nameField.field, secretField.field, hint, actions);
  card.append(summary, body);
  return card;
}

function createApiCredentialForm(onCreate: (data: Required<ApiCredentialPayload>) => Promise<void>, provider = 'resend'): HTMLElement {
  const form = createElement('form', { className: 'settings-form api-credential-form' });
  form.appendChild(createElement('h3', { textContent: 'Adicionar integração' }));
  const providerField = createSelectField('Provedor', provider, API_PROVIDER_OPTIONS);
  const nameField = createInput('Nome da integração', 'text', '', true);
  const asaasType = createSelectField('Credencial Asaas', 'api_key', [
    { value: 'api_key', label: 'Chave de API (envio e consulta de cobranças)' },
    { value: 'webhook_token', label: 'Token do webhook (recebimento de eventos)' }
  ]);
  const asaasEnvironment = createSelectField('Ambiente Asaas', 'sandbox', [
    { value: 'sandbox', label: 'Sandbox (testes)' },
    { value: 'producao', label: 'Produção' }
  ]);
  const secretField = createInput('Segredo de acesso', 'password', '', true);
  secretField.input.autocomplete = 'new-password';
  const hint = createElement('p', { className: 'settings-hint' });
  const webhookHint = createElement('p', { className: 'settings-hint api-webhook-hint', textContent: 'O ambiente ativo é definido por ASAAS_API_BASE_URL no servidor. Use credenciais da mesma conta e ambiente. Configure no Asaas o webhook para /api/v1/webhooks/asaas com o mesmo token cadastrado aqui. O teste do token verifica apenas se ele foi armazenado corretamente.' });
  function refreshProviderCopy(): void {
    const isAsaas = providerField.select.value === 'asaas';
    const nome = `${asaasType.select.value}_${asaasEnvironment.select.value}`;
    const copy = credentialCopy(providerField.select.value as ApiCredentialProvider, false, nome);
    secretField.field.firstElementChild!.textContent = copy.label;
    secretField.input.placeholder = copy.placeholder;
    hint.textContent = copy.hint;
    nameField.field.hidden = isAsaas;
    nameField.input.required = !isAsaas;
    asaasType.field.hidden = !isAsaas;
    asaasEnvironment.field.hidden = !isAsaas;
    webhookHint.hidden = !isAsaas;
  }
  providerField.select.addEventListener('change', refreshProviderCopy);
  asaasType.select.addEventListener('change', refreshProviderCopy);
  asaasEnvironment.select.addEventListener('change', refreshProviderCopy);
  refreshProviderCopy();
  const actions = createElement('div', { className: 'form-actions' });
  const submit = createElement('button', { type: 'submit', textContent: 'Adicionar' });
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const nome = providerField.select.value === 'asaas'
      ? `${asaasType.select.value}_${asaasEnvironment.select.value}`
      : nameField.input.value.trim();
    const segredo = secretField.input.value;
    if (!nome) { nameField.input.focus(); return; }
    if (!segredo) { secretField.input.focus(); return; }
    submit.disabled = true;
    submit.textContent = 'Adicionando...';
    try {
      await onCreate({ provider: providerField.select.value as ApiCredentialProvider, nome, segredo });
    } catch {
      submit.disabled = false;
      submit.textContent = 'Adicionar';
    }
  });
  actions.appendChild(submit);
  form.append(providerField.field, nameField.field, asaasType.field, asaasEnvironment.field, secretField.field, hint, webhookHint, actions);
  return form;
}
