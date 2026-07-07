import { createElement } from '../dom';
import { useToast } from '../hooks/useToast';
import { createBaseLayout } from '../layouts/BaseLayout';
import {
  getDatabaseConfig,
  saveDatabaseProvider,
  saveGoogleDriveConfig,
  saveSqlConfig,
  testDatabaseConnection,
  type DatabaseConfig,
  type DatabaseProvider
} from '../services/databaseConfigService';
import { getSettings, saveSettings, type AppSettings } from '../services/settingsService';

type SettingsTab = 'database' | 'appearance';

export function createSettingsPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const toast = useToast();
  let activeTab: SettingsTab = 'database';
  let databaseConfig: DatabaseConfig | null = null;

  renderContent();
  loadDatabaseConfig();

  return createBaseLayout({
    content,
    eyebrow: 'Configuracoes',
    title: 'Organize integrações, banco de dados e parametros do HUB'
  });

  async function loadDatabaseConfig(): Promise<void> {
    try {
      databaseConfig = await getDatabaseConfig();
      renderContent();
    } catch {
      toast.error('Nao foi possivel carregar configuracoes do backend.');
    }
  }

  function renderContent(): void {
    const tabs = createTabs(activeTab, (tab) => {
      activeTab = tab;
      renderContent();
    });
    const panel = activeTab === 'database'
      ? createDatabasePanel(databaseConfig, toast.success, toast.error, async () => {
        databaseConfig = await getDatabaseConfig();
        renderContent();
      })
      : createAppearancePanel(getSettings(), toast.success);

    content.replaceChildren(tabs, panel);
  }
}

function createTabs(activeTab: SettingsTab, onChange: (tab: SettingsTab) => void): HTMLElement {
  const tabs = createElement('div', { className: 'settings-tabs' });
  const items: Array<{ key: SettingsTab; label: string }> = [
    { key: 'database', label: 'Banco de dados' },
    { key: 'appearance', label: 'Aparencia' }
  ];

  items.forEach((item) => {
    const button = createElement('button', {
      className: activeTab === item.key ? 'settings-tab active' : 'settings-tab',
      textContent: item.label,
      type: 'button'
    });

    button.addEventListener('click', () => onChange(item.key));
    tabs.appendChild(button);
  });

  return tabs;
}

function createDatabasePanel(
  config: DatabaseConfig | null,
  notify: (message: string) => void,
  notifyError: (message: string) => void,
  onRefresh: () => Promise<void>
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

function createAppearancePanel(settings: AppSettings, notify: (message: string) => void): HTMLElement {
  const panel = createElement('section', { className: 'settings-panel' });
  const header = createPanelHeader('Aparencia', 'Cores e identidade visual');
  const body = createElement('div', { className: 'settings-form' });
  const themeColor = createInput('Cor principal', 'color', settings.themeColor);
  const logo = createElement('input');
  const logoField = createElement('label', { className: 'form-field form-field-wide' });
  const logoLabel = createElement('span', { textContent: 'Logotipo PNG/JPG' });
  const preview = createElement('div', { className: 'logo-preview' });
  const saveButton = createElement('button', { textContent: 'Salvar aparencia', type: 'button' });

  logo.type = 'file';
  logo.accept = 'image/png,image/jpeg';
  renderLogoPreview(preview, settings.logoDataUrl);

  saveButton.addEventListener('click', async () => {
    const file = logo.files?.[0];
    const logoDataUrl = file ? await readFileAsDataUrl(file) : settings.logoDataUrl;

    saveSettings({
      ...settings,
      themeColor: themeColor.input.value,
      logoDataUrl
    });
    notify('Aparencia salva.');
    renderLogoPreview(preview, logoDataUrl);
  });

  logoField.append(logoLabel, preview, logo);
  body.append(themeColor.field, logoField, saveButton);
  panel.append(header, body);

  return panel;
}

function createPanelHeader(eyebrowText: string, title: string): HTMLElement {
  const header = createElement('div', { className: 'panel-title' });
  const titleText = createElement('div');
  const eyebrow = createElement('span', { className: 'eyebrow', textContent: eyebrowText });
  const heading = createElement('h2', { textContent: title });

  titleText.append(eyebrow, heading);
  header.appendChild(titleText);

  return header;
}

function createInput(label: string, type: string, value: string) {
  const field = createElement('label', { className: 'form-field' });
  const text = createElement('span', { textContent: label });
  const input = createElement('input');

  input.type = type;
  input.value = value;

  field.append(text, input);
  return { field, input };
}

function renderLogoPreview(container: HTMLElement, logoDataUrl: string): void {
  container.replaceChildren();

  if (!logoDataUrl) {
    container.textContent = 'Sem logotipo definido.';
    return;
  }

  const image = createElement('img');
  image.src = logoDataUrl;
  image.alt = 'Logotipo configurado';
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
