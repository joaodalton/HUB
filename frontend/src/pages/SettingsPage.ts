import { createElement } from '../dom';
import { createInput, createSelectField } from '../components/formFields';
import { createDataTable } from '../components/DataTable';
import { useToast } from '../hooks/useToast';
import { createBaseLayout } from '../layouts/BaseLayout';
import { getCurrentUser } from '../services/authService';
import { getEmpresaAtual, updateEmpresaAtual, type EmpresaAtual, type EmpresaAtualUpdate } from '../services/empresaService';
import { refreshSidebarBrand } from '../components/Sidebar';
import {
  applyAppearanceSettings,
  applyThemeVariables,
  DEFAULT_SETTINGS,
  getSettings,
  loadSettings,
  resetAppearanceToDefaults,
  saveSettings,
  type AppSettings
} from '../services/settingsService';
import {
  activateGoogleAccount,
  disconnectGoogleAccount,
  getGoogleAccounts,
  getGoogleAuthorizeUrl,
  type GoogleAccountRow
} from '../services/googleAccountService';
import { formattedLogDate, getRecentLogs, type LogRow } from '../services/logsService';
import { DEFAULT_RATEIO_CONFIG, getRateioConfig, saveRateioConfig, type RateioConfig } from '../services/rateioConfigService';
import {
  createApiCredential,
  deleteApiCredential,
  getApiCredentials,
  updateApiCredential,
  type ApiCredentialPayload,
  type ApiCredentialProvider,
  type ApiCredentialRow
} from '../services/apiCredentialsService';

type SettingsCategory = 'home' | 'geral' | 'database' | 'apis' | 'automations' | 'logs' | 'appearance';

type CategoryDefinition = {
  key: SettingsCategory;
  label: string;
  // false = categoria so existe na navegacao, ainda sem backend por tras.
  // Mostra um aviso "em breve" em vez de fingir que a funcionalidade existe.
  ready: boolean;
};

const CATEGORIES: CategoryDefinition[] = [
  { key: 'home', label: 'Home', ready: true },
  { key: 'geral', label: 'Geral', ready: true },
  { key: 'database', label: 'Banco de Dados', ready: true },
  { key: 'apis', label: 'APIs e Integrações', ready: true },
  { key: 'automations', label: 'Automações', ready: false },
  { key: 'logs', label: 'Logs', ready: true },
  { key: 'appearance', label: 'Aparência', ready: true }
];

export function createSettingsPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const toast = useToast();
  let activeCategory: SettingsCategory = 'home';
  let googleAccounts: GoogleAccountRow[] = [];
  let appearanceLoaded = false;
  let recentLogs: LogRow[] = [];
  let logsLoaded = false;
  let rateioConfig: RateioConfig = DEFAULT_RATEIO_CONFIG;
  let rateioConfigLoaded = false;
  let apiCredentials: ApiCredentialRow[] = [];
  let apiCredentialsLoaded = false;
  let apiCredentialsLoadError = false;
  let empresaAtual: EmpresaAtual | null = null;
  let empresaAtualLoaded = false;
  let empresaAtualLoadError = false;

  renderContent();
  loadGoogleAccounts();
  refreshAppearance();
  loadRecentLogs();
  loadRateioConfig();
  if (canManageSettings()) loadApiCredentials();
  else apiCredentialsLoaded = true;
  if (canManageSettings()) loadEmpresaAtual();
  else empresaAtualLoaded = true;

  const layout = createBaseLayout({
    content,
    eyebrow: 'Configuracoes',
    title: 'Organize integrações, banco de dados e parametros do HUB'
  });

  // So depois do createBaseLayout() acima -- e o createToastContainer() la dentro --
  // rodarem, senao toastState.container ainda ta null e showToast() nao faz nada.
  handleGoogleOAuthRedirect(toast, () => changeCategory('database'));

  return layout;

  async function loadGoogleAccounts(): Promise<void> {
    try {
      googleAccounts = await getGoogleAccounts();
    } catch {
      googleAccounts = [];
    } finally {
      renderContent();
    }
  }

  async function handleActivateAccount(id: number): Promise<void> {
    try {
      await activateGoogleAccount(id);
      toast.success('Conta Google ativada.');
    } catch {
      toast.error('Nao foi possivel ativar a conta.');
    } finally {
      await loadGoogleAccounts();
    }
  }

  async function handleDisconnectAccount(id: number): Promise<void> {
    try {
      await disconnectGoogleAccount(id);
      toast.success('Conta Google desconectada.');
    } catch {
      toast.error('Nao foi possivel desconectar a conta.');
    } finally {
      await loadGoogleAccounts();
    }
  }

  async function refreshAppearance(): Promise<void> {
    try {
      await loadSettings();
    } catch {
      toast.error('Nao foi possivel carregar a aparencia salva. Usando padrao.');
    } finally {
      appearanceLoaded = true;
      renderContent();
    }
  }

  async function loadRecentLogs(): Promise<void> {
    try {
      recentLogs = await getRecentLogs(50);
    } catch {
      recentLogs = [];
    } finally {
      logsLoaded = true;
      renderContent();
    }
  }

  async function loadRateioConfig(): Promise<void> {
    try {
      rateioConfig = await getRateioConfig();
    } catch {
      rateioConfig = DEFAULT_RATEIO_CONFIG;
    } finally {
      rateioConfigLoaded = true;
      renderContent();
    }
  }

  async function handleSaveRateioConfig(novoConfig: RateioConfig): Promise<void> {
    try {
      rateioConfig = await saveRateioConfig(novoConfig);
      toast.success('Configuração salva.');
    } catch {
      toast.error('Não foi possível salvar a configuração.');
    } finally {
      renderContent();
    }
  }


  async function loadApiCredentials(): Promise<void> {
    try {
      apiCredentials = await getApiCredentials();
      apiCredentialsLoadError = false;
    } catch {
      apiCredentials = [];
      apiCredentialsLoadError = true;
    } finally {
      apiCredentialsLoaded = true;
      renderContent();
    }
  }

  async function loadEmpresaAtual(): Promise<void> {
    try {
      empresaAtual = await getEmpresaAtual();
      empresaAtualLoadError = false;
    } catch {
      empresaAtual = null;
      empresaAtualLoadError = true;
    } finally {
      empresaAtualLoaded = true;
      renderContent();
    }
  }

  async function handleSaveEmpresaAtual(data: EmpresaAtualUpdate): Promise<void> {
    try {
      empresaAtual = await updateEmpresaAtual(data);
      toast.success('Dados da empresa atualizados.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Não foi possível atualizar os dados da empresa.');
      throw error;
    } finally {
      renderContent();
    }
  }

  async function handleCreateApiCredential(data: Required<ApiCredentialPayload>): Promise<void> {
    try {
      apiCredentials = [...apiCredentials, await createApiCredential(data)];
      toast.success('Integração adicionada.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Não foi possível adicionar a integração.');
      throw error;
    } finally {
      renderContent();
    }
  }

  async function handleUpdateApiCredential(id: number, data: Pick<ApiCredentialPayload, 'nome' | 'segredo'>): Promise<void> {
    try {
      const updated = await updateApiCredential(id, data);
      apiCredentials = apiCredentials.map((item) => item.id === id ? updated : item);
      toast.success('Integração atualizada.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Não foi possível atualizar a integração.');
      throw error;
    } finally {
      renderContent();
    }
  }

  async function handleDeleteApiCredential(id: number): Promise<void> {
    try {
      await deleteApiCredential(id);
      apiCredentials = apiCredentials.filter((item) => item.id !== id);
      toast.success('Integração removida.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Não foi possível remover a integração.');
    } finally {
      renderContent();
    }
  }
  
  function changeCategory(category: SettingsCategory): void {
    // Sai da aba Aparencia sem salvar -> descarta a pre-visualizacao de cor
    // pra nao deixar o tema "vazando" preview nao salvo pelo resto do app.
    if (activeCategory === 'appearance' && category !== 'appearance') {
      applyAppearanceSettings();
    }

    activeCategory = category;
    renderContent();
  }

  function renderContent(): void {
    const nav = createCategoryNav(activeCategory, changeCategory);
    const panel = renderCategoryPanel();
    const shell = createElement('div', { className: 'settings-shell' });

    shell.append(nav, panel);
    content.replaceChildren(shell);
  }

  function renderCategoryPanel(): HTMLElement {
    switch (activeCategory) {
      case 'home':
        return createHomePanel(recentLogs, logsLoaded, () => changeCategory('logs'));

      case 'geral':
        return createGeralPanel(
          empresaAtual,
          empresaAtualLoaded,
          empresaAtualLoadError,
          canManageSettings(),
          loadEmpresaAtual,
          handleSaveEmpresaAtual,
          rateioConfig,
          rateioConfigLoaded,
          handleSaveRateioConfig
        );

      case 'database':
        return createDatabasePanel({
          items: googleAccounts,
          onActivate: handleActivateAccount,
          onDisconnect: handleDisconnectAccount
        });

      case 'apis':
        return createApiCredentialsPanel(
          apiCredentials,
          apiCredentialsLoaded,
          apiCredentialsLoadError,
          canManageSettings(),
          loadApiCredentials,
          handleCreateApiCredential,
          handleUpdateApiCredential,
          handleDeleteApiCredential
        );

      case 'logs':
        return createLogsPanel(recentLogs, logsLoaded);

      case 'appearance':
        return createAppearancePanel(getSettings(), appearanceLoaded, toast.success, toast.error);

      default:
        return createComingSoonPanel(categoryMessage(activeCategory));
    }
  }
}

// Depois do callback do Google, o backend redireciona pra /configuracoes?google_oauth=sucesso|erro.
// Mostra o toast uma vez, leva o usuario pra aba Banco de Dados (onde a lista de contas fica) e
// limpa a URL pra nao repetir se a pagina for recarregada.
function handleGoogleOAuthRedirect(
  toast: { success: (message: string) => void; error: (message: string) => void },
  onRedirected: () => void
): void {
  const params = new URLSearchParams(window.location.search);
  const status = params.get('google_oauth');

  if (!status) return;

  if (status === 'sucesso') {
    toast.success('Conta Google conectada.');
  } else {
    const motivo = params.get('motivo');
    toast.error(motivo ? `Nao foi possivel conectar a conta Google: ${motivo}` : 'Nao foi possivel conectar a conta Google.');
  }

  params.delete('google_oauth');
  params.delete('motivo');
  const query = params.toString();
  window.history.replaceState({}, '', `${window.location.pathname}${query ? `?${query}` : ''}`);
  onRedirected();
}

function createCategoryNav(active: SettingsCategory, onChange: (category: SettingsCategory) => void): HTMLElement {
  const nav = createElement('nav', { className: 'settings-category-nav' });
  nav.appendChild(createElement('span', { className: 'settings-category-heading', textContent: 'Categorias' }));

  CATEGORIES.forEach((category) => {
    const link = createElement('button', {
      className: category.key === active ? 'settings-category-link active' : 'settings-category-link',
      type: 'button'
    });

    link.appendChild(createElement('span', { textContent: category.label }));
    if (!category.ready) {
      link.appendChild(createElement('span', { className: 'settings-category-tag', textContent: 'em breve' }));
    }

    link.addEventListener('click', () => onChange(category.key));
    nav.appendChild(link);
  });

  return nav;
}

function categoryMessage(category: SettingsCategory): string {
  switch (category) {
    case 'apis':
      return 'Em construção — integrações externas (Asaas, WhatsApp, concessionárias, inversores) entram a partir da V2.0, quando cada uma for conectada de verdade.';
    case 'automations':
      return 'Em construção — automações dependem das integrações de APIs acima, ainda não implementadas.';
    default:
      return 'Em construção.';
  }
}

// ---------- Geral ----------

function createGeralPanel(
  empresa: EmpresaAtual | null,
  empresaLoaded: boolean,
  empresaLoadError: boolean,
  canManage: boolean,
  onRetryEmpresa: () => Promise<void>,
  onSaveEmpresa: (data: EmpresaAtualUpdate) => Promise<void>,
  config: RateioConfig,
  loaded: boolean,
  onSave: (config: RateioConfig) => Promise<void>
): HTMLElement {
  const stack = createElement('div', { className: 'content-stack' });
  if (!canManage) {
    const denied = createElement('section', { className: 'settings-panel' });
    denied.append(
      createPanelHeader('Dados da Empresa', 'Informações cadastrais da empresa atual'),
      createElement('p', { className: 'settings-hint', textContent: 'Seu perfil não tem permissão para visualizar ou alterar os dados da empresa.' })
    );
    stack.appendChild(denied);
    return stack;
  }

  stack.append(
    createEmpresaAtualPanel(empresa, empresaLoaded, empresaLoadError, onRetryEmpresa, onSaveEmpresa),
    createRateioConfigPanel(config, loaded, onSave)
  );
  return stack;
}

function createEmpresaAtualPanel(
  empresa: EmpresaAtual | null,
  loaded: boolean,
  loadError: boolean,
  onRetry: () => Promise<void>,
  onSave: (data: EmpresaAtualUpdate) => Promise<void>
): HTMLElement {
  const panel = createElement('section', { className: 'settings-panel' });
  panel.appendChild(createPanelHeader('Dados da Empresa', 'Informações cadastrais da empresa atual. Slug e status não podem ser alterados aqui.'));

  if (!loaded) {
    panel.appendChild(createElement('p', { className: 'settings-hint', textContent: 'Carregando dados da empresa...' }));
    return panel;
  }
  if (loadError || !empresa) {
    const retry = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Tentar novamente' });
    retry.addEventListener('click', () => void onRetry());
    panel.append(createElement('p', { className: 'settings-hint', textContent: 'Não foi possível carregar os dados da empresa.' }), retry);
    return panel;
  }

  const form = createElement('form', { className: 'settings-form empresa-atual-form' });
  const nome = createInput('Nome', 'text', empresa.nome, true);
  const razaoSocial = createInput('Razão social', 'text', empresa.razaoSocial ?? '', false);
  const cnpj = createInput('CNPJ', 'text', empresa.cnpj ?? '', false);
  cnpj.input.inputMode = 'numeric';
  cnpj.input.placeholder = 'Somente números';
  const email = createInput('E-mail', 'email', empresa.email ?? '', false);
  const telefone = createInput('Telefone', 'tel', empresa.telefone ?? '', false);
  const actions = createElement('div', { className: 'form-actions' });
  const submit = createElement('button', { type: 'submit', textContent: 'Salvar dados' });
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const nomeValue = nome.input.value.trim();
    const cnpjValue = cnpj.input.value.replace(/\D/g, '');
    const telefoneValue = telefone.input.value.trim();
    if (!nomeValue) { nome.input.focus(); return; }
    if (cnpjValue && cnpjValue.length !== 14) { cnpj.input.setCustomValidity('Informe os 14 dígitos do CNPJ.'); cnpj.input.reportValidity(); return; }
    cnpj.input.setCustomValidity('');
    if (!email.input.checkValidity()) { email.input.reportValidity(); return; }
    if (telefoneValue && telefoneValue.replace(/\D/g, '').length < 8) { telefone.input.setCustomValidity('Informe um telefone válido.'); telefone.input.reportValidity(); return; }
    telefone.input.setCustomValidity('');
    submit.disabled = true;
    submit.textContent = 'Salvando...';
    try {
      await onSave({ nome: nomeValue, razaoSocial: razaoSocial.input.value.trim(), cnpj: cnpjValue, email: email.input.value.trim(), telefone: telefoneValue });
    } catch {
      submit.disabled = false;
      submit.textContent = 'Salvar dados';
    }
  });
  actions.appendChild(submit);
  form.append(nome.field, razaoSocial.field, cnpj.field, email.field, telefone.field, actions);
  panel.appendChild(form);
  return panel;
}

function createRateioConfigPanel(
  config: RateioConfig,
  loaded: boolean,
  onSave: (config: RateioConfig) => Promise<void>
): HTMLElement {
  const panel = createElement('section', { className: 'settings-panel' });
  panel.appendChild(createPanelHeader('Rateio', 'Regras padrão usadas pelo motor de rateio'));

  if (!loaded) {
    panel.appendChild(createElement('p', { className: 'settings-hint', textContent: 'Carregando...' }));
    return panel;
  }

  const body = createElement('div', { className: 'settings-form' });

  const habilitado = createElement('label', { className: 'form-field form-field-checkbox' });
  const habilitadoInput = createElement('input');
  habilitadoInput.type = 'checkbox';
  habilitadoInput.checked = config.bufferHabilitado;
  habilitado.append(habilitadoInput, createElement('span', { textContent: 'Aplicar buffer de segurança no consumo por padrão' }));

  const percentual = createElement('label', { className: 'form-field' });
  const percentualLabel = createElement('span', { textContent: 'Percentual do buffer (%)' });
  const percentualInput = createElement('input');
  percentualInput.type = 'number';
  percentualInput.min = '0';
  percentualInput.max = '100';
  percentualInput.step = '0.5';
  percentualInput.value = String(config.bufferPercentual);
  percentual.append(percentualLabel, percentualInput);

  const hint = createElement('p', {
    className: 'settings-hint',
    textContent: 'Esse valor vale pra todas as UCs por padrão. Cada UC pode ter um percentual próprio (campo dentro do cadastro da UC), que sempre ganha desse valor global quando preenchido.'
  });

  const actions = createElement('div', { className: 'form-actions' });
  const saveButton = createElement('button', { textContent: 'Salvar', type: 'button' });
  const resetButton = createElement('button', { className: 'secondary-button', textContent: 'Restaurar padrão', type: 'button' });

  saveButton.addEventListener('click', async () => {
    saveButton.disabled = true;
    saveButton.textContent = 'Salvando...';

    await onSave({
      bufferHabilitado: habilitadoInput.checked,
      bufferPercentual: Number(percentualInput.value) || 0
    });

    saveButton.disabled = false;
    saveButton.textContent = 'Salvar';
  });

  resetButton.addEventListener('click', async () => {
    habilitadoInput.checked = DEFAULT_RATEIO_CONFIG.bufferHabilitado;
    percentualInput.value = String(DEFAULT_RATEIO_CONFIG.bufferPercentual);
    await onSave(DEFAULT_RATEIO_CONFIG);
  });

  body.append(habilitado, percentual, hint);
  actions.append(saveButton, resetButton);
  panel.append(body, actions);

  return panel;
}

// ---------- APIs e integrações ----------

const API_PROVIDER_OPTIONS: Array<{ value: ApiCredentialProvider; label: string }> = [
  { value: 'resend', label: 'Resend (e-mail)' },
  { value: 'whatsapp', label: 'WhatsApp' },
  { value: 'asaas', label: 'Asaas (financeiro)' },
  { value: 'concessionaria', label: 'Concessionária' }
];

function createApiCredentialsPanel(
  credentials: ApiCredentialRow[],
  loaded: boolean,
  loadError: boolean,
  canManage: boolean,
  onRetry: () => Promise<void>,
  onCreate: (data: Required<ApiCredentialPayload>) => Promise<void>,
  onUpdate: (id: number, data: Pick<ApiCredentialPayload, 'nome' | 'segredo'>) => Promise<void>,
  onDelete: (id: number) => Promise<void>
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

  const list = createElement('div', { className: 'api-credentials-list' });
  if (credentials.length === 0) {
    list.appendChild(createElement('p', { className: 'settings-hint', textContent: 'Nenhuma integração configurada ainda.' }));
  } else {
    credentials.forEach((credential) => list.appendChild(createApiCredentialCard(credential, onUpdate, onDelete)));
  }
  panel.appendChild(list);
  panel.appendChild(createApiCredentialForm(onCreate));
  return panel;
}

function createApiCredentialCard(
  credential: ApiCredentialRow,
  onUpdate: (id: number, data: Pick<ApiCredentialPayload, 'nome' | 'segredo'>) => Promise<void>,
  onDelete: (id: number) => Promise<void>
): HTMLElement {
  const card = createElement('details', { className: 'api-credential-card' });
  const summary = createElement('summary', { className: 'api-credential-summary' });
  const provider = API_PROVIDER_OPTIONS.find((option) => option.value === credential.provider)?.label ?? credential.provider;
  const status = createElement('span', { className: credential.configurada ? 'provider-badge success' : 'provider-badge warning', textContent: credential.configurada ? 'Configurada' : 'Sem segredo' });
  const title = createElement('div', { className: 'api-credential-title' });
  title.append(createElement('strong', { textContent: credential.nome }), createElement('span', { textContent: provider }));
  summary.append(title, status);

  const body = createElement('form', { className: 'settings-form api-credential-form' });
  const providerField = createElement('label', { className: 'form-field' });
  providerField.append(
    createElement('span', { textContent: 'Provedor' }),
    createElement('strong', { textContent: provider })
  );
  const nameField = createInput('Nome da integração', 'text', credential.nome, true);
  const secretField = createInput('Novo segredo (opcional)', 'password', '', false);
  secretField.input.autocomplete = 'new-password';
  secretField.input.placeholder = 'Deixe em branco para manter o atual';
  const hint = createElement('p', { className: 'settings-hint', textContent: 'Por segurança, o segredo configurado não pode ser consultado ou exibido. Informe outro valor somente para substituí-lo.' });
  const actions = createElement('div', { className: 'form-actions' });
  const save = createElement('button', { type: 'submit', textContent: 'Salvar alterações' });
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
  remove.addEventListener('click', async () => {
    if (!window.confirm(`Remover a integração "${credential.nome}"?`)) return;
    remove.disabled = true;
    await onDelete(credential.id);
    remove.disabled = false;
  });
  actions.append(save, remove);
  body.append(providerField, nameField.field, secretField.field, hint, actions);
  card.append(summary, body);
  return card;
}

function createApiCredentialForm(onCreate: (data: Required<ApiCredentialPayload>) => Promise<void>): HTMLElement {
  const form = createElement('form', { className: 'settings-form api-credential-form' });
  form.appendChild(createElement('h3', { textContent: 'Adicionar integração' }));
  const providerField = createSelectField('Provedor', 'resend', API_PROVIDER_OPTIONS);
  const nameField = createInput('Nome da integração', 'text', '', true);
  const secretField = createInput('Segredo de acesso', 'password', '', true);
  secretField.input.autocomplete = 'new-password';
  const hint = createElement('p', { className: 'settings-hint', textContent: 'O segredo é enviado apenas para ser protegido no servidor; ele não será listado, preenchido novamente nem gravado pelo navegador.' });
  const actions = createElement('div', { className: 'form-actions' });
  const submit = createElement('button', { type: 'submit', textContent: 'Adicionar' });
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const nome = nameField.input.value.trim();
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
  form.append(providerField.field, nameField.field, secretField.field, hint, actions);
  return form;
}

function createComingSoonPanel(message: string): HTMLElement {
  const panel = createElement('section', { className: 'placeholder-panel' });
  panel.appendChild(createElement('p', { textContent: message }));
  return panel;
}

// ---------- Home ----------

function createHomePanel(
  logs: LogRow[],
  logsLoaded: boolean,
  onSeeAllLogs: () => void
): HTMLElement {
  const logsCard = createElement('section', { className: 'settings-panel' });
  const seeAllButton = createElement('button', { className: 'secondary-link', textContent: 'Ver todos', type: 'button' });
  seeAllButton.addEventListener('click', onSeeAllLogs);
  logsCard.appendChild(createPanelHeader('Logs recentes', 'Últimos eventos do sistema', seeAllButton));

  if (!logsLoaded) {
    logsCard.appendChild(createElement('p', { className: 'settings-hint', textContent: 'Carregando logs...' }));
  } else if (logs.length === 0) {
    logsCard.appendChild(createElement('p', { className: 'settings-hint', textContent: 'Nenhum log registrado ainda.' }));
  } else {
    const list = createElement('div', { className: 'log-list' });
    logs.slice(0, 5).forEach((log) => list.appendChild(createLogRow(log)));
    logsCard.appendChild(list);
  }

  return logsCard;
}

function createLogRow(log: LogRow): HTMLElement {
  const row = createElement('div', { className: 'log-row' });
  row.append(
    createElement('span', { className: `log-level log-level-${log.nivel}`, textContent: log.nivel }),
    createElement('span', { className: 'log-message', textContent: log.mensagem || log.acao }),
    createElement('span', { className: 'log-meta', textContent: formattedLogDate(log) })
  );
  return row;
}

// ---------- Logs ----------

function createLogsPanel(logs: LogRow[], loaded: boolean): HTMLElement {
  return createDataTable<LogRow & { dataFormatada: string }>({
    title: 'Logs do sistema',
    eyebrow: 'Histórico',
    rows: logs.map((log) => ({ ...log, dataFormatada: formattedLogDate(log) })),
    emptyMessage: loaded ? 'Nenhum log registrado ainda.' : 'Carregando logs...',
    columns: [
      { key: 'dataFormatada', label: 'Data/Hora' },
      { key: 'nivel', label: 'Nível' },
      { key: 'acao', label: 'Ação' },
      { key: 'mensagem', label: 'Mensagem' }
    ]
  });
}

// ---------- Banco de dados ----------
// So mostra contas Google conectadas via OAuth -- troca de provedor (Google
// Drive vs SQL) saiu da interface porque ja esta configurada e estavel no
// backend (.env), nao precisa mais de tela pra trocar isso. Os services
// continuam existindo (databaseConfigService.ts no front,
// database_config_service.py + config_routes.py no back) -- so a UI parou
// de expor, se um dia precisar trocar de provedor de novo e so reativar.

function createDatabasePanel(googleAccounts: {
  items: GoogleAccountRow[];
  onActivate: (id: number) => void;
  onDisconnect: (id: number) => void;
}): HTMLElement {
  const wrapper = createElement('section', { className: 'database-provider-stack' });
  wrapper.appendChild(createGoogleAccountsSection(googleAccounts.items, googleAccounts.onActivate, googleAccounts.onDisconnect));
  return wrapper;
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
  const eyebrow = createElement('span', { className: 'eyebrow', textContent: 'OAuth' });
  const heading = createElement('h2', { textContent: 'Contas Google conectadas' });
  const connectLink = createElement('a', { className: 'small-button', textContent: 'Conectar nova conta' });

  connectLink.href = getGoogleAuthorizeUrl();

  text.append(eyebrow, heading);
  header.append(text, connectLink);
  section.appendChild(header);

  if (accounts.length === 0) {
    section.appendChild(createElement('p', {
      className: 'settings-hint',
      textContent: 'Nenhuma conta conectada ainda. "Conectar nova conta" leva pro login real do Google -- sem precisar compartilhar pasta manualmente.'
    }));
    return section;
  }

  const list = createElement('dl', { className: 'settings-list compact' });

  accounts.forEach((account) => {
    const label = createElement('dt', { textContent: account.email });
    const valueRow = createElement('dd', { className: 'account-row' });
    const status = createElement('span', {
      className: account.ativa ? 'provider-badge success' : 'provider-badge',
      textContent: account.ativa ? 'Ativa' : 'Inativa'
    });
    const activateButton = createElement('button', {
      className: 'secondary-button',
      textContent: 'Usar esta conta',
      type: 'button'
    });
    const disconnectButton = createElement('button', {
      className: 'danger-button',
      textContent: 'Desconectar',
      type: 'button'
    });

    activateButton.disabled = account.ativa;
    activateButton.addEventListener('click', () => onActivate(account.id));
    disconnectButton.addEventListener('click', () => {
      if (window.confirm(`Desconectar a conta ${account.email}?`)) onDisconnect(account.id);
    });

    valueRow.append(status, activateButton, disconnectButton);
    list.append(label, valueRow);
  });

  section.appendChild(list);
  return section;
}

// ---------- Aparencia ----------

function createAppearancePanel(
  settings: AppSettings,
  loaded: boolean,
  notify: (message: string) => void,
  notifyError: (message: string) => void
): HTMLElement {
  const panel = createElement('section', { className: 'settings-panel' });
  const header = createPanelHeader('Aparência', 'Identidade visual e preferências do HUB');

  if (!loaded) {
    panel.append(header, createElement('p', {
      className: 'settings-hint',
      textContent: 'Carregando aparencia salva...'
    }));
    return panel;
  }

  const body = createElement('div', { className: 'settings-form' });

  const logoField = createElement('label', { className: 'form-field' });
  const logoLabel = createElement('span', { textContent: 'Logotipo' });
  const logoRow = createElement('div', { className: 'logo-row' });
  const preview = createElement('div', { className: 'logo-preview' });
  const logoInput = createElement('input');
  const logoButton = createElement('button', { className: 'secondary-button', textContent: 'Alterar logo', type: 'button' });

  logoInput.type = 'file';
  logoInput.accept = 'image/png,image/jpeg';
  logoInput.hidden = true;
  renderLogoPreview(preview, settings.logoDataUrl);

  logoButton.addEventListener('click', () => logoInput.click());
  logoInput.addEventListener('change', async () => {
    const file = logoInput.files?.[0];
    if (!file) return;

    logoButton.disabled = true;
    logoButton.textContent = 'Enviando...';

    try {
      const logoDataUrl = await readFileAsDataUrl(file);
      await saveSettings({ logoDataUrl });
      renderLogoPreview(preview, logoDataUrl);
      notify('Logo atualizada.');
    } catch {
      notifyError('Nao foi possivel salvar a logo.');
    } finally {
      logoButton.disabled = false;
      logoButton.textContent = 'Alterar logo';
      logoInput.value = '';
    }
  });

  logoRow.append(preview, logoButton, logoInput);
  logoField.append(logoLabel, logoRow);

  const language = createSelectField('Idioma', settings.language, [
    { value: 'pt-BR', label: 'Português (Brasil)' },
    { value: 'en-US', label: 'English' }
  ]);
  const languageHint = createElement('p', {
    className: 'settings-hint',
    textContent: 'A troca de idioma so guarda a preferencia por enquanto -- ainda nao traduz os textos da interface.'
  });

  const companyName = createInput('Nome da empresa', 'text', settings.companyName);

  const colorsTitle = createElement('span', { className: 'settings-subheading', textContent: 'Cores do tema' });
  const colorGrid = createElement('div', { className: 'color-field-grid' });
  const backgroundColor = createColorField('Fundo', settings.backgroundColor);
  const cardColor = createColorField('Fundo dos cards', settings.cardColor);
  const textColor = createColorField('Texto geral', settings.textColor);
  const accentColor = createColorField('Cor de seleção', settings.accentColor);

  const colorFields = [
    { field: backgroundColor, key: 'backgroundColor' as const },
    { field: cardColor, key: 'cardColor' as const },
    { field: textColor, key: 'textColor' as const },
    { field: accentColor, key: 'accentColor' as const }
  ];

  function previewColors(): void {
    applyThemeVariables({
      backgroundColor: backgroundColor.input.value,
      cardColor: cardColor.input.value,
      textColor: textColor.input.value,
      accentColor: accentColor.input.value
    });
  }

  colorFields.forEach(({ field }) => field.input.addEventListener('input', previewColors));

  colorGrid.append(backgroundColor.field, cardColor.field, textColor.field, accentColor.field);

  const actions = createElement('div', { className: 'form-actions' });
  const saveButton = createElement('button', { textContent: 'Salvar aparência', type: 'button' });
  const resetButton = createElement('button', { className: 'secondary-button', textContent: 'Restaurar padrão', type: 'button' });

  saveButton.addEventListener('click', async () => {
    saveButton.disabled = true;
    saveButton.textContent = 'Salvando...';

    try {
      await saveSettings({
        companyName: companyName.input.value.trim(),
        language: language.select.value,
        backgroundColor: backgroundColor.input.value,
        cardColor: cardColor.input.value,
        textColor: textColor.input.value,
        accentColor: accentColor.input.value
      });
      notify('Aparência salva.');
      refreshSidebarBrand();
    } catch {
      notifyError('Nao foi possivel salvar a aparencia no backend.');
      applyAppearanceSettings();
    } finally {
      saveButton.disabled = false;
      saveButton.textContent = 'Salvar aparência';
    }
  });

  resetButton.addEventListener('click', async () => {
    colorFields.forEach(({ field, key }) => {
      field.input.value = DEFAULT_SETTINGS[key];
      field.input.dispatchEvent(new Event('input'));
    });

    try {
      await resetAppearanceToDefaults();
      notify('Cores restauradas para o padrão.');
    } catch {
      notifyError('Nao foi possivel restaurar o padrao no backend.');
    }
  });

  body.append(logoField, language.field, languageHint, companyName.field, colorsTitle, colorGrid);
  actions.append(saveButton, resetButton);
  panel.append(header, body, actions);

  return panel;
}

function createColorField(label: string, value: string): { field: HTMLElement; input: HTMLInputElement } {
  const field = createElement('label', { className: 'form-field color-field' });
  const text = createElement('span', { textContent: label });
  const row = createElement('div', { className: 'color-field-row' });
  const input = createElement('input');
  const hexLabel = createElement('span', { className: 'color-hex', textContent: value });

  input.type = 'color';
  input.value = value;
  input.addEventListener('input', () => { hexLabel.textContent = input.value; });

  row.append(input, hexLabel);
  field.append(text, row);

  return { field, input };
}

function renderLogoPreview(container: HTMLElement, logoDataUrl: string): void {
  container.replaceChildren();

  if (!logoDataUrl) {
    container.textContent = 'Sem logo';
    return;
  }

  const image = createElement('img');
  image.src = logoDataUrl;
  image.alt = 'Logotipo configurado';
  image.className = 'logo-preview-image';
  container.appendChild(image);
}

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();

    reader.addEventListener('load', () => resolve(String(reader.result)));
    reader.addEventListener('error', () => reject(reader.error));
    reader.readAsDataURL(file);
  });
}

// ---------- Helpers compartilhados ----------

function createPanelHeader(eyebrowText: string, title: string, action?: HTMLElement): HTMLElement {
  const header = createElement('div', { className: 'panel-title' });
  const titleText = createElement('div');
  const eyebrow = createElement('span', { className: 'eyebrow', textContent: eyebrowText });
  const heading = createElement('h2', { textContent: title });

  titleText.append(eyebrow, heading);
  header.appendChild(titleText);
  if (action) header.appendChild(action);

  return header;
}

function canManageSettings(): boolean {
  const role = getCurrentUser()?.role;
  return role === 'owner' || role === 'admin';
}
