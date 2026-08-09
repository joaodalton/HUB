import { createElement } from '../dom';
import { createDataTable } from '../components/DataTable';
import { useToast } from '../hooks/useToast';
import { createBaseLayout } from '../layouts/BaseLayout';
import { refreshSidebarBrand } from '../components/Sidebar';
import {
  getDatabaseConfig,
  saveDatabaseProvider,
  saveGoogleDriveConfig,
  saveSqlConfig,
  testDatabaseConnection,
  type DatabaseConfig,
  type DatabaseProvider
} from '../services/databaseConfigService';
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
import { createUser, getUsers, setUserActive, type UserRow } from '../services/userService';

type SettingsCategory = 'home' | 'geral' | 'database' | 'apis' | 'users' | 'automations' | 'logs' | 'appearance';

type CategoryDefinition = {
  key: SettingsCategory;
  label: string;
  // false = categoria so existe na navegacao, ainda sem backend por tras.
  // Mostra um aviso "em breve" em vez de fingir que a funcionalidade existe
  // (mesmo padrao ja usado em /pendencias, ver PlaceholderPage.ts).
  ready: boolean;
};

const CATEGORIES: CategoryDefinition[] = [
  { key: 'home', label: 'Home', ready: true },
  { key: 'geral', label: 'Geral', ready: false },
  { key: 'database', label: 'Banco de Dados', ready: true },
  { key: 'apis', label: 'APIs e Integrações', ready: false },
  { key: 'users', label: 'Usuários', ready: true },
  { key: 'automations', label: 'Automações', ready: false },
  { key: 'logs', label: 'Logs', ready: true },
  { key: 'appearance', label: 'Aparência', ready: true }
];

export function createSettingsPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const toast = useToast();
  let activeCategory: SettingsCategory = 'home';
  let databaseConfig: DatabaseConfig | null = null;
  let googleAccounts: GoogleAccountRow[] = [];
  let appearanceLoaded = false;
  let recentLogs: LogRow[] = [];
  let logsLoaded = false;
  let users: UserRow[] = [];
  let usersLoaded = false;

  renderContent();
  loadDatabaseConfig();
  loadGoogleAccounts();
  refreshAppearance();
  loadRecentLogs();
  loadUsers();

  const layout = createBaseLayout({
    content,
    eyebrow: 'Configuracoes',
    title: 'Organize integrações, banco de dados e parametros do HUB'
  });

  // So depois do createBaseLayout() acima -- e o createToastContainer() la dentro --
  // rodarem, senao toastState.container ainda ta null e showToast() nao faz nada.
  handleGoogleOAuthRedirect(toast, () => changeCategory('database'));

  return layout;

  async function loadDatabaseConfig(): Promise<void> {
    try {
      databaseConfig = await getDatabaseConfig();
      renderContent();
    } catch {
      toast.error('Nao foi possivel carregar configuracoes do backend.');
    }
  }

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

  // Falha silenciosa de proposito quando quem esta logado e viewer -- o backend
  // devolve 403 pra essa rota (e' admin-only), e a aba simplesmente mostra
  // "nenhum usuario" em vez de um toast de erro (ver createUsersPanel abaixo,
  // ele detecta esse caso e explica em vez de reclamar).
  async function loadUsers(): Promise<void> {
    try {
      users = await getUsers();
    } catch {
      users = [];
    } finally {
      usersLoaded = true;
      renderContent();
    }
  }

  async function handleCreateUser(data: { email: string; senha: string; papel: 'admin' | 'viewer' }): Promise<void> {
    try {
      await createUser(data);
      toast.success('Usuário criado.');
      await loadUsers();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Não foi possível criar o usuário.');
    }
  }

  async function handleToggleUserActive(user: UserRow): Promise<void> {
    try {
      await setUserActive(user.id, !user.ativo);
      toast.success(user.ativo ? 'Usuário desativado.' : 'Usuário ativado.');
      await loadUsers();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Não foi possível atualizar o usuário.');
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
        return createHomePanel(databaseConfig, recentLogs, logsLoaded, () => changeCategory('logs'));

      case 'database':
        return createDatabasePanel(databaseConfig, toast.success, toast.error, async () => {
          databaseConfig = await getDatabaseConfig();
          renderContent();
        }, {
          items: googleAccounts,
          onActivate: handleActivateAccount,
          onDisconnect: handleDisconnectAccount
        });

      case 'logs':
        return createLogsPanel(recentLogs, logsLoaded);

      case 'users':
        return createUsersPanel(users, usersLoaded, handleCreateUser, handleToggleUserActive);

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
    case 'geral':
      return 'Em construção — fuso horário, concessionária padrão e outras preferências gerais chegam numa próxima etapa.';
    case 'apis':
      return 'Em construção — integrações externas (Asaas, WhatsApp, concessionárias, inversores) entram a partir da V2.0, quando cada uma for conectada de verdade.';
    case 'users':
      return 'Em construção — gestão de usuários e permissões por papel chega numa fase futura.';
    case 'automations':
      return 'Em construção — automações dependem das integrações de APIs acima, ainda não implementadas.';
    default:
      return 'Em construção.';
  }
}

function createComingSoonPanel(message: string): HTMLElement {
  const panel = createElement('section', { className: 'placeholder-panel' });
  panel.appendChild(createElement('p', { textContent: message }));
  return panel;
}

// ---------- Home ----------

function createHomePanel(
  config: DatabaseConfig | null,
  logs: LogRow[],
  logsLoaded: boolean,
  onSeeAllLogs: () => void
): HTMLElement {
  const wrapper = createElement('div', { className: 'settings-home-grid' });

  const driveCard = createElement('section', { className: 'settings-panel' });
  driveCard.appendChild(createPanelHeader('Google Drive', 'Status da conexão'));

  if (!config) {
    driveCard.appendChild(createElement('p', { className: 'settings-hint', textContent: 'Carregando...' }));
  } else {
    const list = createElement('dl', { className: 'settings-list compact' });
    list.append(
      createElement('dt', { textContent: 'Status' }),
      createElement('dd', {
        textContent: config.provider === 'google_drive' ? 'Ativo como banco de dados' : 'Configurado, mas não ativo'
      }),
      createElement('dt', { textContent: 'Credenciais' }),
      createElement('dd', { textContent: config.googleDrive.credentialsFound ? 'Arquivo encontrado' : 'Arquivo não encontrado' }),
      createElement('dt', { textContent: 'Pasta raiz' }),
      createElement('dd', { textContent: config.googleDrive.rootFolderId || 'Não configurada' })
    );
    driveCard.appendChild(list);
  }

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

  wrapper.append(driveCard, logsCard);
  return wrapper;
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

// ---------- Usuários ----------
// So visivel de verdade pra quem loga como admin -- o backend bloqueia
// GET /users pra viewer (403), entao a lista vem vazia e o painel mostra um
// aviso em vez de fingir que a tela existe pra todo mundo.

function createUsersPanel(
  users: UserRow[],
  loaded: boolean,
  onCreate: (data: { email: string; senha: string; papel: 'admin' | 'viewer' }) => Promise<void>,
  onToggleActive: (user: UserRow) => Promise<void>
): HTMLElement {
  const panel = createElement('section', { className: 'settings-panel' });
  panel.appendChild(createPanelHeader('Usuários', 'Quem tem acesso ao HUB e com que papel'));

  if (!loaded) {
    panel.appendChild(createElement('p', { className: 'settings-hint', textContent: 'Carregando...' }));
    return panel;
  }

  if (users.length === 0) {
    panel.appendChild(createElement('p', {
      className: 'settings-hint',
      textContent: 'Nenhum usuário encontrado, ou sua conta não tem permissão pra ver essa lista (só administrador gerencia usuários).'
    }));
    return panel;
  }

  const list = createElement('dl', { className: 'settings-list compact' });

  users.forEach((user) => {
    const label = createElement('dt', { textContent: user.email });
    const valueRow = createElement('dd', { className: 'account-row' });
    const roleBadge = createElement('span', {
      className: user.papel === 'admin' ? 'provider-badge success' : 'provider-badge',
      textContent: user.papel === 'admin' ? 'Administrador' : 'Visualizador'
    });
    const statusBadge = createElement('span', {
      className: user.ativo ? 'provider-badge success' : 'provider-badge warning',
      textContent: user.ativo ? 'Ativo' : 'Inativo'
    });
    const toggleButton = createElement('button', {
      className: user.ativo ? 'danger-button' : 'secondary-button',
      textContent: user.ativo ? 'Desativar' : 'Ativar',
      type: 'button'
    });

    toggleButton.addEventListener('click', () => onToggleActive(user));

    valueRow.append(roleBadge, statusBadge, toggleButton);
    list.append(label, valueRow);
  });

  panel.appendChild(list);
  panel.appendChild(createNewUserForm(onCreate));

  return panel;
}

function createNewUserForm(
  onCreate: (data: { email: string; senha: string; papel: 'admin' | 'viewer' }) => Promise<void>
): HTMLElement {
  const form = createElement('form', { className: 'settings-form' });
  form.appendChild(createElement('span', { className: 'settings-subheading', textContent: 'Novo usuário' }));

  const email = createInput('Email', 'email', '');
  const senha = createInput('Senha provisória', 'password', '');
  const papel = createSelectField('Papel', 'viewer', [
    { value: 'viewer', label: 'Visualizador (só leitura)' },
    { value: 'admin', label: 'Administrador (acesso total)' }
  ]);

  const actions = createElement('div', { className: 'form-actions' });
  const submitButton = createElement('button', { textContent: 'Criar usuário', type: 'submit' });
  actions.appendChild(submitButton);

  form.append(email.field, senha.field, papel.field, actions);

  form.addEventListener('submit', async (event) => {
    event.preventDefault();

    if (!email.input.value.trim() || !senha.input.value.trim()) {
      email.input.reportValidity();
      senha.input.reportValidity();
      return;
    }

    submitButton.disabled = true;
    submitButton.textContent = 'Criando...';

    await onCreate({
      email: email.input.value.trim(),
      senha: senha.input.value,
      papel: papel.select.value as 'admin' | 'viewer'
    });

    email.input.value = '';
    senha.input.value = '';
    papel.select.value = 'viewer';
    submitButton.disabled = false;
    submitButton.textContent = 'Criar usuário';
  });

  return form;
}

// ---------- Banco de dados (sem mudanca de comportamento, so mudou de lugar) ----------

function createDatabasePanel(
  config: DatabaseConfig | null,
  notify: (message: string) => void,
  notifyError: (message: string) => void,
  onRefresh: () => Promise<void>,
  googleAccounts: {
    items: GoogleAccountRow[];
    onActivate: (id: number) => void;
    onDisconnect: (id: number) => void;
  }
): HTMLElement {
  const wrapper = createElement('section', { className: 'database-provider-stack' });

  if (!config) {
    wrapper.appendChild(createElement('section', {
      className: 'settings-panel placeholder-panel',
      textContent: 'Carregando configuracoes do backend...'
    }));
    return wrapper;
  }

  wrapper.append(
    createProviderCard({
      title: 'Google Drive',
      eyebrow: 'Banco atual',
      active: config.provider === 'google_drive',
      configured: config.googleDrive.configured,
      lines: [
        ['Credenciais', config.googleDrive.credentialsFound ? 'Arquivo encontrado' : 'Arquivo nao encontrado'],
        ['Pasta raiz', config.googleDrive.rootFolderId || 'Nao configurada'],
        ['Arquivo de dados', config.googleDrive.dataFile]
      ],
      onConfigure: () => document.body.appendChild(createGoogleDriveModal(config, notify, notifyError, onRefresh)),
      onUse: async () => {
        await saveDatabaseProvider('google_drive');
        notify('Google Drive definido como banco ativo.');
        await onRefresh();
      },
      onTest: () => testProvider('google_drive', notify, notifyError)
    }),
    createGoogleAccountsSection(googleAccounts.items, googleAccounts.onActivate, googleAccounts.onDisconnect),
    createProviderCard({
      title: 'SQL',
      eyebrow: 'Banco futuro',
      active: config.provider === 'sql',
      configured: config.sql.configured,
      lines: [
        ['Driver', config.sql.driver || 'Nao configurado'],
        ['Servidor', config.sql.host || 'Nao configurado'],
        ['Banco', config.sql.database || 'Nao configurado']
      ],
      onConfigure: () => document.body.appendChild(createSqlModal(config, notify, notifyError, onRefresh)),
      onUse: async () => {
        await saveDatabaseProvider('sql');
        notify('SQL definido como banco ativo.');
        await onRefresh();
      },
      onTest: () => testProvider('sql', notify, notifyError)
    })
  );

  return wrapper;
}

// Contas Google conectadas via OAuth real (multiplas, com refresh token no banco) --
// complementa o credentials.json de service account acima, nao substitui ainda.
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

function createProviderCard({
  title,
  eyebrow,
  active,
  configured,
  lines,
  onConfigure,
  onUse,
  onTest
}: {
  title: string;
  eyebrow: string;
  active: boolean;
  configured: boolean;
  lines: Array<[string, string]>;
  onConfigure: () => void;
  onUse: () => void;
  onTest: () => void;
}): HTMLElement {
  const card = createElement('section', { className: active ? 'database-provider-card active' : 'database-provider-card' });
  const header = createElement('div', { className: 'provider-header' });
  const text = createElement('div');
  const eyebrowElement = createElement('span', { className: 'eyebrow', textContent: eyebrow });
  const heading = createElement('h2', { textContent: title });
  const badge = createElement('span', {
    className: configured ? 'provider-badge success' : 'provider-badge warning',
    textContent: active ? 'Ativo' : configured ? 'Configurado' : 'Pendente'
  });
  const list = createElement('dl', { className: 'settings-list compact' });
  const actions = createElement('div', { className: 'provider-actions' });
  const configureButton = createElement('button', { textContent: 'Configurar', type: 'button' });
  const useButton = createElement('button', { className: 'secondary-button', textContent: 'Usar este banco', type: 'button' });
  const testButton = createElement('button', { className: 'secondary-button', textContent: 'Testar conexao', type: 'button' });

  lines.forEach(([label, value]) => {
    list.append(createElement('dt', { textContent: label }), createElement('dd', { textContent: value }));
  });

  configureButton.addEventListener('click', onConfigure);
  useButton.addEventListener('click', onUse);
  testButton.addEventListener('click', onTest);
  useButton.disabled = active;

  text.append(eyebrowElement, heading);
  header.append(text, badge);
  actions.append(configureButton, useButton, testButton);
  card.append(header, list, actions);

  return card;
}

function createGoogleDriveModal(
  config: DatabaseConfig,
  notify: (message: string) => void,
  notifyError: (message: string) => void,
  onRefresh: () => Promise<void>
): HTMLElement {
  const credentialsFile = createInput('Arquivo de credenciais no backend', 'text', config.googleDrive.credentialsFile);
  const rootFolderId = createInput('ID da pasta raiz no Drive', 'text', config.googleDrive.rootFolderId);
  const dataFile = createInput('Arquivo de dados', 'text', config.googleDrive.dataFile);

  return createConfigModal({
    title: 'Configurar Google Drive',
    fields: [credentialsFile.field, rootFolderId.field, dataFile.field],
    hint: 'O JSON da service account deve ficar no backend. Nao cole segredo no navegador.',
    onSave: async () => {
      try {
        await saveGoogleDriveConfig({
          credentialsFile: credentialsFile.input.value.trim(),
          rootFolderId: rootFolderId.input.value.trim(),
          dataFile: dataFile.input.value.trim()
        });
        notify('Google Drive salvo no backend.');
        await onRefresh();
        return true;
      } catch {
        notifyError('Nao foi possivel salvar Google Drive.');
        return false;
      }
    }
  });
}

function createSqlModal(
  config: DatabaseConfig,
  notify: (message: string) => void,
  notifyError: (message: string) => void,
  onRefresh: () => Promise<void>
): HTMLElement {
  const driver = createInput('Driver', 'text', config.sql.driver);
  const host = createInput('Host', 'text', config.sql.host);
  const port = createInput('Porta', 'text', config.sql.port);
  const database = createInput('Banco', 'text', config.sql.database);
  const user = createInput('Usuario', 'text', config.sql.user);
  const password = createInput('Senha', 'password', '');

  return createConfigModal({
    title: 'Configurar SQL',
    fields: [driver.field, host.field, port.field, database.field, user.field, password.field],
    hint: config.sql.passwordConfigured ? 'Senha ja configurada. Preencha novamente apenas se quiser trocar.' : 'A senha sera enviada ao backend para gravacao local.',
    onSave: async () => {
      try {
        await saveSqlConfig({
          driver: driver.input.value.trim(),
          host: host.input.value.trim(),
          port: port.input.value.trim(),
          database: database.input.value.trim(),
          user: user.input.value.trim(),
          password: password.input.value
        });
        notify('SQL salvo no backend.');
        await onRefresh();
        return true;
      } catch {
        notifyError('Nao foi possivel salvar SQL.');
        return false;
      }
    }
  });
}

function createConfigModal({
  title,
  fields,
  hint,
  onSave
}: {
  title: string;
  fields: HTMLElement[];
  hint: string;
  onSave: () => Promise<boolean>;
}): HTMLElement {
  const overlay = createElement('section', { className: 'modal-overlay' });
  const panel = createElement('article', { className: 'plant-card' });
  const form = createElement('form', { className: 'client-form' });
  const header = createElement('div', { className: 'form-header' });
  const heading = createElement('h2', { textContent: title });
  const closeButton = createElement('button', { className: 'secondary-button', textContent: 'Fechar', type: 'button' });
  const body = createElement('div', { className: 'settings-form' });
  const hintText = createElement('p', { className: 'settings-hint', textContent: hint });
  const actions = createElement('div', { className: 'form-actions' });
  const saveButton = createElement('button', { textContent: 'Salvar configuracao', type: 'submit' });

  closeButton.addEventListener('click', () => overlay.remove());
  overlay.addEventListener('click', (event) => {
    if (event.target === overlay) overlay.remove();
  });
  form.addEventListener('submit', async (event) => {
    event.preventDefault();

    if (await onSave()) {
      overlay.remove();
    }
  });

  header.append(heading, closeButton);
  body.append(...fields, hintText);
  actions.appendChild(saveButton);
  form.append(header, body, actions);
  panel.appendChild(form);
  overlay.appendChild(panel);

  return overlay;
}

async function testProvider(
  provider: DatabaseProvider,
  notify: (message: string) => void,
  notifyError: (message: string) => void
): Promise<void> {
  try {
    notify(await testDatabaseConnection(provider));
  } catch (error) {
    notifyError(error instanceof Error ? error.message : 'Teste falhou. Verifique a configuracao no backend.');
  }
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

  // Logo -- um botao so, salva sozinho assim que um arquivo e escolhido.
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

  // Idioma -- por enquanto so guarda a preferencia (ver aviso abaixo).
  const language = createSelectField('Idioma', settings.language, [
    { value: 'pt-BR', label: 'Português (Brasil)' },
    { value: 'en-US', label: 'English' }
  ]);
  const languageHint = createElement('p', {
    className: 'settings-hint',
    textContent: 'A troca de idioma so guarda a preferencia por enquanto -- ainda nao traduz os textos da interface.'
  });

  const companyName = createInput('Nome da empresa', 'text', settings.companyName);

  // Cores do tema -- so as 4 bases; hover/fundo translucido/etc sao derivados
  // (ver applyThemeVariables em settingsService.ts) pra nao virar uma tela
  // cheia de color-picker solto.
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

function createSelectField(
  label: string,
  value: string,
  options: Array<{ value: string; label: string }>
): { field: HTMLElement; select: HTMLSelectElement } {
  const field = createElement('label', { className: 'form-field' });
  const text = createElement('span', { textContent: label });
  const select = createElement('select');

  options.forEach((option) => {
    const optionElement = createElement('option', { textContent: option.label });
    optionElement.value = option.value;
    select.appendChild(optionElement);
  });

  select.value = value;
  field.append(text, select);

  return { field, select };
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

function createInput(label: string, type: string, value: string): { field: HTMLElement; input: HTMLInputElement } {
  const field = createElement('label', { className: 'form-field' });
  const text = createElement('span', { textContent: label });
  const input = createElement('input');

  input.type = type;
  input.value = value;

  field.append(text, input);
  return { field, input };
}