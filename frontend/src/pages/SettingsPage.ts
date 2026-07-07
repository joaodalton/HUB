import { createElement } from '../dom';
import { useToast } from '../hooks/useToast';
import { createBaseLayout } from '../layouts/BaseLayout';
import {
  addDriveAccount,
  getSettings,
  saveSettings,
  type AppSettings
} from '../services/settingsService';

type SettingsTab = 'database' | 'appearance';

export function createSettingsPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const toast = useToast();
  let activeTab: SettingsTab = 'database';

  renderContent();

  return createBaseLayout({
    content,
    eyebrow: 'Configuracoes',
    title: 'Organize integrações, banco de dados e parametros do HUB'
  });

  function renderContent(): void {
    const tabs = createTabs(activeTab, (tab) => {
      activeTab = tab;
      renderContent();
    });
    const panel = activeTab === 'database'
      ? createDatabasePanel(getSettings(), toast.success)
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

function createDatabasePanel(settings: AppSettings, notify: (message: string) => void): HTMLElement {
  const panel = createElement('section', { className: 'settings-panel' });
  const header = createPanelHeader('Banco de dados', 'Fontes de dados e contas conectadas');
  const body = createElement('div', { className: 'settings-form' });
  const activeDrive = createDriveSelect(settings);
  const accountName = createInput('Nome da conta Google Drive', 'text', '');
  const accountEmail = createInput('Email/identificador', 'email', '');
  const sqlHost = createInput('Servidor SQL futuro', 'text', settings.sqlHost);
  const sqlDatabase = createInput('Banco SQL futuro', 'text', settings.sqlDatabase);
  const addAccountButton = createElement('button', {
    className: 'secondary-button',
    textContent: 'Adicionar conta Drive',
    type: 'button'
  });
  const saveButton = createElement('button', { textContent: 'Salvar banco de dados', type: 'button' });
  const hint = createElement('p', {
    className: 'settings-hint',
    textContent: 'Credenciais e URLs sensiveis continuam em variaveis de ambiente; aqui ficam selecoes operacionais.'
  });

  addAccountButton.addEventListener('click', () => {
    if (!accountName.input.value.trim() || !accountEmail.input.value.trim()) return;

    addDriveAccount(accountName.input.value.trim(), accountEmail.input.value.trim());
    notify('Conta Google Drive adicionada.');
  });
  saveButton.addEventListener('click', () => {
    saveSettings({
      ...settings,
      activeDriveAccountId: activeDrive.select.value,
      sqlHost: sqlHost.input.value.trim(),
      sqlDatabase: sqlDatabase.input.value.trim()
    });
    notify('Configuracoes de banco salvas.');
  });

  body.append(activeDrive.field, accountName.field, accountEmail.field, addAccountButton, sqlHost.field, sqlDatabase.field, hint, saveButton);
  panel.append(header, body);

  return panel;
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

function createDriveSelect(settings: AppSettings) {
  const field = createElement('label', { className: 'form-field form-field-wide' });
  const label = createElement('span', { textContent: 'Conta Google Drive ativa' });
  const select = createElement('select');

  settings.driveAccounts.forEach((account) => {
    const option = createElement('option', { textContent: `${account.nome} - ${account.email}` });
    option.value = account.id;
    select.appendChild(option);
  });

  select.value = settings.activeDriveAccountId;
  field.append(label, select);

  return { field, select };
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
