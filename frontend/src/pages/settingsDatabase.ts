import { createElement } from '../dom';
import { createInput, createSelectField } from '../components/formFields';
import { createRegulatoryTariffModal } from '../components/RegulatoryTariffModal';
import { type RegulatoryTariffStatus } from '../services/regulatoryTariffsService';
import { type DocumentStorageProvider } from '../services/settingsService';
import { createPanelHeader } from './settingsShared';
import { formatDate } from '../utils/date';

// ---------- Banco de dados ----------
export function createDatabasePanel(googleAccounts: {
  storageProvider: DocumentStorageProvider;
  storageProviderLoaded: boolean;
  onSaveStorageProvider: (provider: DocumentStorageProvider) => Promise<void>;
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
  wrapper.appendChild(createStorageProviderPanel(
    googleAccounts.storageProvider,
    googleAccounts.storageProviderLoaded,
    googleAccounts.canManage,
    googleAccounts.onSaveStorageProvider
  ));
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

function createStorageProviderPanel(
  provider: DocumentStorageProvider,
  loaded: boolean,
  canManage: boolean,
  onSave: (provider: DocumentStorageProvider) => Promise<void>
): HTMLElement {
  const section = createElement('section', { className: 'database-provider-card' });
  section.appendChild(createPanelHeader('Documentos', 'Armazenamento de documentos'));

  if (!loaded) {
    section.appendChild(createElement('p', { className: 'settings-hint', textContent: 'Carregando configuracao...' }));
    return section;
  }

  const providerField = createSelectField('Onde guardar os documentos', provider, [
    { value: 's3', label: 'Nosso armazenamento (B2/S3) — recomendado' },
    { value: 'google_drive', label: 'Minha conta Google Drive' }
  ]);
  providerField.select.disabled = !canManage;
  section.appendChild(providerField.field);

  if (!canManage) return section;

  const saveButton = createElement('button', { textContent: 'Salvar armazenamento', type: 'button' });
  saveButton.addEventListener('click', async () => {
    saveButton.disabled = true;
    saveButton.textContent = 'Salvando...';
    try {
      await onSave(providerField.select.value as DocumentStorageProvider);
    } finally {
      saveButton.disabled = false;
      saveButton.textContent = 'Salvar armazenamento';
    }
  });
  section.appendChild(saveButton);
  return section;
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
