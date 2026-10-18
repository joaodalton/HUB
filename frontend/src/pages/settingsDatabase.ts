import { createElement } from '../dom';
import { createInput } from '../components/formFields';
import { createRegulatoryTariffModal } from '../components/RegulatoryTariffModal';
import { getGoogleAuthorizeUrl, type GoogleAccountRow } from '../services/googleAccountService';
import { type RegulatoryTariffStatus } from '../services/regulatoryTariffsService';
import { createPanelHeader } from './settingsShared';

// ---------- Banco de dados ----------
export function createDatabasePanel(googleAccounts: {
  items: GoogleAccountRow[];
  onActivate: (id: number) => void;
  onDisconnect: (id: number) => void;
  rootFolderId: string;
  rootFolderLoaded: boolean;
  canManage: boolean;
  onSaveRootFolder: (rootFolderId: string) => Promise<void>;
  regulatoryStatus: RegulatoryTariffStatus | null;
  regulatoryLoaded: boolean;
  regulatoryLoadError: 'permission' | 'unavailable' | 'internal' | 'unknown' | null;
  canManageRegulatory: boolean;
  onRefreshRegulatory: () => Promise<void>;
}): HTMLElement {
  const wrapper = createElement('section', { className: 'database-provider-stack' });
  wrapper.appendChild(createGoogleAccountsSection(googleAccounts.items, googleAccounts.onActivate, googleAccounts.onDisconnect));
  wrapper.appendChild(createDriveRootFolderPanel(
    googleAccounts.rootFolderId,
    googleAccounts.rootFolderLoaded,
    googleAccounts.canManage,
    googleAccounts.onSaveRootFolder
  ));
  if (googleAccounts.canManageRegulatory) wrapper.appendChild(createRegulatoryTariffPanel(
    googleAccounts.regulatoryStatus, googleAccounts.regulatoryLoaded, googleAccounts.regulatoryLoadError,
    googleAccounts.onRefreshRegulatory));
  return wrapper;
}

function createRegulatoryTariffPanel(
  status: RegulatoryTariffStatus | null, loaded: boolean,
  loadError: 'permission' | 'unavailable' | 'internal' | 'unknown' | null, refresh: () => Promise<void>
): HTMLElement {
  const panel = createElement('section', { className: 'database-provider-card' });
  panel.appendChild(createPanelHeader('Base tarifária ANEEL', 'Tarifas oficiais usadas no cálculo de Fio B'));
  if (!loaded) { panel.appendChild(createElement('p', { className: 'settings-hint', textContent: 'Carregando base regulatória...' })); return panel; }
  if (loadError) {
    const message = loadError === 'permission' ? 'Você não tem permissão para consultar a base regulatória.'
      : loadError === 'unavailable' ? 'Base regulatória indisponível. Tente novamente mais tarde.'
      : loadError === 'internal' ? 'Erro interno ao consultar a base regulatória.'
      : 'Não foi possível consultar a base regulatória.';
    const retry = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Tentar novamente' });
    retry.addEventListener('click', () => void refresh());
    panel.append(createElement('p', { className: 'importacao-error', textContent: message }), retry);
    return panel;
  }
  const text = status?.status === 'updated'
    ? `Atualizada: ${status.records} registro(s), cobertura ${formatDate(status.coverage.from)} a ${formatDate(status.coverage.until)}.`
    : 'Sem importação concluída.';
  panel.appendChild(createElement('p', { className: 'settings-hint', textContent: text }));
  const update = createElement('button', { type: 'button', textContent: 'Atualizar tarifas' });
  update.addEventListener('click', () => document.body.appendChild(createRegulatoryTariffModal(refresh)));
  panel.appendChild(update);
  return panel;
}

function formatDate(value: string | null): string {
  if (!value) return '—';
  const [year, month, day] = value.split('-');
  return `${day}/${month}/${year}`;
}

function createDriveRootFolderPanel(
  rootFolderId: string,
  loaded: boolean,
  canManage: boolean,
  onSave: (rootFolderId: string) => Promise<void>
): HTMLElement {
  const section = createElement('section', { className: 'database-provider-card' });
  section.appendChild(createPanelHeader('Google Drive', 'Pasta exclusiva da empresa atual para busca e documentos'));

  if (!loaded) {
    section.appendChild(createElement('p', { className: 'settings-hint', textContent: 'Carregando configuracao...' }));
    return section;
  }

  const folderField = createInput('ID da pasta raiz', 'text', rootFolderId);
  folderField.input.placeholder = 'ID presente na URL da pasta do Google Drive';
  folderField.input.disabled = !canManage;
  const hint = createElement('p', {
    className: 'settings-hint',
    textContent: 'Necessario para manter documentos e buscas isolados por empresa.'
  });
  section.append(folderField.field, hint);

  if (!canManage) return section;

  const saveButton = createElement('button', { textContent: 'Salvar pasta', type: 'button' });
  saveButton.addEventListener('click', async () => {
    saveButton.disabled = true;
    saveButton.textContent = 'Salvando...';
    try {
      await onSave(folderField.input.value);
    } finally {
      saveButton.disabled = false;
      saveButton.textContent = 'Salvar pasta';
    }
  });
  section.appendChild(saveButton);
  return section;
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
      textContent: 'Nenhuma conta conectada ainda. Conecte, aprove no Google e use os arquivos da conta: não é preciso informar ID de pasta.'
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
