import { createElement } from '../dom';
import { createInput, createSelectField } from '../components/formFields';
import { createRegulatoryTariffModal } from '../components/RegulatoryTariffModal';
import { type RegulatoryTariffStatus } from '../services/regulatoryTariffsService';
import { type DocumentStorageProvider } from '../services/settingsService';
import { createPanelHeader } from './settingsShared';
import { formatDate } from '../utils/date';
import { t } from '../services/i18nService';

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
  panel.appendChild(createPanelHeader(t('settings.database.regulatoryHeading'), t('settings.database.regulatoryDescription')));
  if (!loaded) { panel.appendChild(createElement('p', { className: 'settings-hint', textContent: t('settings.database.regulatoryLoading') })); return panel; }
  if (loadError) {
    const message = loadError === 'permission' ? t('settings.database.regulatoryErrorPermission')
      : loadError === 'unavailable' ? t('settings.database.regulatoryErrorUnavailable')
      : loadError === 'internal' ? t('settings.database.regulatoryErrorInternal')
      : t('settings.database.regulatoryErrorUnknown');
    const retry = createElement('button', { className: 'secondary-button', type: 'button', textContent: t('common.retry') });
    retry.addEventListener('click', () => void refresh());
    panel.append(createElement('p', { className: 'importacao-error', textContent: message }), retry);
    return panel;
  }
  const text = status?.status === 'updated'
    ? `${t('settings.database.regulatoryUpdated')}: ${status.records} ${t('settings.database.regulatoryRecordsCoverage')} ${formatDate(status.coverage.from)} ${t('settings.database.regulatoryTo')} ${formatDate(status.coverage.until)}.`
    : t('settings.database.regulatoryNoImport');
  panel.appendChild(createElement('p', { className: 'settings-hint', textContent: text }));
  const update = createElement('button', { type: 'button', textContent: t('settings.database.regulatoryUpdateButton') });
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
  section.appendChild(createPanelHeader(t('settings.database.documentsHeading'), t('settings.database.documentsDescription')));

  if (!loaded) {
    section.appendChild(createElement('p', { className: 'settings-hint', textContent: t('settings.database.loadingConfig') }));
    return section;
  }

  const providerField = createSelectField(t('settings.database.whereToStore'), provider, [
    { value: 's3', label: t('settings.database.storageS3') },
    { value: 'google_drive', label: t('settings.database.storageGoogleDrive') }
  ]);
  providerField.select.disabled = !canManage;
  section.appendChild(providerField.field);

  if (!canManage) return section;

  const saveButton = createElement('button', { textContent: t('settings.database.saveStorage'), type: 'button' });
  saveButton.addEventListener('click', async () => {
    saveButton.disabled = true;
    saveButton.textContent = t('common.saving');
    try {
      await onSave(providerField.select.value as DocumentStorageProvider);
    } finally {
      saveButton.disabled = false;
      saveButton.textContent = t('settings.database.saveStorage');
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
  section.appendChild(createPanelHeader(t('settings.database.googleDriveHeading'), t('settings.database.googleDriveDescription')));

  if (!loaded) {
    section.appendChild(createElement('p', { className: 'settings-hint', textContent: t('settings.database.loadingConfig') }));
    return section;
  }

  const folderField = createInput(t('settings.database.rootFolderIdLabel'), 'text', rootFolderId);
  folderField.input.placeholder = t('settings.database.rootFolderIdPlaceholder');
  folderField.input.disabled = !canManage;
  const hint = createElement('p', {
    className: 'settings-hint',
    textContent: t('settings.database.rootFolderHint')
  });
  section.append(folderField.field, hint);

  if (!canManage) return section;

  const saveButton = createElement('button', { textContent: t('settings.database.saveFolder'), type: 'button' });
  saveButton.addEventListener('click', async () => {
    saveButton.disabled = true;
    saveButton.textContent = t('common.saving');
    try {
      await onSave(folderField.input.value);
    } finally {
      saveButton.disabled = false;
      saveButton.textContent = t('settings.database.saveFolder');
    }
  });
  section.appendChild(saveButton);
  return section;
}
