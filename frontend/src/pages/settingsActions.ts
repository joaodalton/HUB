import { getEmpresaAtual, updateEmpresaAtual, type EmpresaAtual, type EmpresaAtualUpdate } from '../services/empresaService';
import { loadSettings, loadGoogleDriveRootFolderId, saveGoogleDriveRootFolderId, loadDocumentStorageProvider, saveDocumentStorageProvider, type DocumentStorageProvider } from '../services/settingsService';
import { activateGoogleAccount, disconnectGoogleAccount, getGoogleAccounts, type GoogleAccountRow } from '../services/googleAccountService';
import { getRecentLogs, type LogRow } from '../services/logsService';
import { DEFAULT_RATEIO_CONFIG, getRateioConfig, saveRateioConfig, type RateioConfig } from '../services/rateioConfigService';
import { createApiCredential, deleteApiCredential, getApiCredentials, testApiCredential, updateApiCredential, type ApiCredentialPayload, type ApiCredentialRow } from '../services/apiCredentialsService';
import { deleteWhatsappIntegration, getWhatsappIntegration, saveWhatsappIntegration, testWhatsappIntegration, type WhatsappIntegration, type WhatsappIntegrationInput } from '../services/whatsappService';
import { getRegulatoryTariffStatus, type RegulatoryTariffStatus } from '../services/regulatoryTariffsService';
import { ApiRequestError } from '../services/apiClient';
import { t } from '../services/i18nService';

export function createSettingsActions(
  toast: { success: (message: string) => void; error: (message: string) => void },
  renderContent: () => void
) {
  const state = {
    googleAccounts: [] as GoogleAccountRow[],
    appearanceLoaded: false,
    recentLogs: [] as LogRow[],
    logsLoaded: false,
    rateioConfig: DEFAULT_RATEIO_CONFIG as RateioConfig,
    rateioConfigLoaded: false,
    apiCredentials: [] as ApiCredentialRow[],
    apiCredentialsLoaded: false,
    apiCredentialsLoadError: false,
    whatsappIntegration: null as WhatsappIntegration | null,
    whatsappIntegrationLoaded: false,
    empresaAtual: null as EmpresaAtual | null,
    empresaAtualLoaded: false,
    empresaAtualLoadError: false,
    driveRootFolderId: '',
    driveRootFolderLoaded: false,
    documentStorageProvider: 's3' as DocumentStorageProvider,
    documentStorageProviderLoaded: false,
    regulatoryTariffStatus: null as RegulatoryTariffStatus | null,
    regulatoryTariffLoaded: false,
    regulatoryTariffLoadError: null as 'permission' | 'unavailable' | 'internal' | 'unknown' | null
  };

  async function loadGoogleAccounts(): Promise<void> {
    try {
      state.googleAccounts = await getGoogleAccounts();
    } catch {
      state.googleAccounts = [];
    } finally {
      renderContent();
    }
  }

  async function handleActivateAccount(id: number): Promise<void> {
    try {
      await activateGoogleAccount(id);
      toast.success(t('settings.actions.googleAccountActivated'));
    } catch {
      toast.error(t('settings.actions.googleAccountActivateError'));
    } finally {
      await loadGoogleAccounts();
    }
  }

  async function handleDisconnectAccount(id: number): Promise<void> {
    try {
      await disconnectGoogleAccount(id);
      toast.success(t('settings.actions.googleAccountDisconnected'));
    } catch {
      toast.error(t('settings.actions.googleAccountDisconnectError'));
    } finally {
      await loadGoogleAccounts();
    }
  }

  async function refreshAppearance(): Promise<void> {
    try {
      await loadSettings();
    } catch {
      toast.error(t('settings.actions.appearanceLoadError'));
    } finally {
      state.appearanceLoaded = true;
      renderContent();
    }
  }

  async function loadRecentLogs(): Promise<void> {
    try {
      state.recentLogs = await getRecentLogs(50);
    } catch {
      state.recentLogs = [];
    } finally {
      state.logsLoaded = true;
      renderContent();
    }
  }

  async function loadRateioConfig(): Promise<void> {
    try {
      state.rateioConfig = await getRateioConfig();
    } catch {
      state.rateioConfig = DEFAULT_RATEIO_CONFIG;
    } finally {
      state.rateioConfigLoaded = true;
      renderContent();
    }
  }

  async function loadDriveRootFolder(): Promise<void> {
    try {
      state.driveRootFolderId = await loadGoogleDriveRootFolderId();
    } catch {
      state.driveRootFolderId = '';
    } finally {
      state.driveRootFolderLoaded = true;
      renderContent();
    }
  }

  async function handleSaveDriveRootFolderId(rootFolderId: string): Promise<void> {
    try {
      await saveGoogleDriveRootFolderId(rootFolderId);
      state.driveRootFolderId = rootFolderId.trim();
      toast.success(t('settings.actions.driveRootFolderSaved'));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('settings.actions.driveRootFolderSaveError'));
      throw error;
    } finally {
      renderContent();
    }
  }

  async function loadDocumentStorageProviderSetting(): Promise<void> {
    try {
      state.documentStorageProvider = await loadDocumentStorageProvider();
    } catch {
      state.documentStorageProvider = 's3';
    } finally {
      state.documentStorageProviderLoaded = true;
      renderContent();
    }
  }

  async function handleSaveDocumentStorageProvider(provider: DocumentStorageProvider): Promise<void> {
    try {
      await saveDocumentStorageProvider(provider);
      state.documentStorageProvider = provider;
      toast.success(t('settings.actions.documentStorageUpdated'));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('settings.actions.documentStorageSaveError'));
      throw error;
    } finally {
      renderContent();
    }
  }

  async function handleSaveRateioConfig(novoConfig: RateioConfig): Promise<void> {
    try {
      state.rateioConfig = await saveRateioConfig(novoConfig);
      toast.success(t('settings.actions.configSaved'));
    } catch {
      toast.error(t('settings.actions.configSaveError'));
    } finally {
      renderContent();
    }
  }


  async function loadApiCredentials(): Promise<void> {
    try {
      state.apiCredentials = await getApiCredentials();
      state.apiCredentialsLoadError = false;
    } catch {
      state.apiCredentials = [];
      state.apiCredentialsLoadError = true;
    } finally {
      state.apiCredentialsLoaded = true;
      renderContent();
    }
  }

  async function loadWhatsappIntegration(): Promise<void> {
    try { state.whatsappIntegration = await getWhatsappIntegration(); }
    catch { state.whatsappIntegration = null; }
    finally { state.whatsappIntegrationLoaded = true; renderContent(); }
  }

  async function handleSaveWhatsappIntegration(input: WhatsappIntegrationInput): Promise<void> {
    try { state.whatsappIntegration = await saveWhatsappIntegration(input); toast.success(t('settings.actions.whatsappSaved')); }
    catch (error) { toast.error(error instanceof Error ? error.message : t('settings.actions.whatsappSaveError')); throw error; }
    finally { renderContent(); }
  }

  async function handleTestWhatsappIntegration(): Promise<void> {
    try { state.whatsappIntegration = await testWhatsappIntegration(); toast.success(t('settings.actions.whatsappTestSuccess')); }
    catch (error) { toast.error(error instanceof Error ? error.message : t('settings.actions.whatsappTestError')); }
    finally { renderContent(); }
  }

  async function handleDeleteWhatsappIntegration(): Promise<void> {
    if (!window.confirm(t('settings.actions.whatsappDeleteConfirm'))) return;
    try { await deleteWhatsappIntegration(); state.whatsappIntegration = null; toast.success(t('settings.actions.whatsappRemoved')); }
    catch (error) { toast.error(error instanceof Error ? error.message : t('settings.actions.whatsappRemoveError')); }
    finally { renderContent(); }
  }

  async function loadEmpresaAtual(): Promise<void> {
    try {
      state.empresaAtual = await getEmpresaAtual();
      state.empresaAtualLoadError = false;
    } catch {
      state.empresaAtual = null;
      state.empresaAtualLoadError = true;
    } finally {
      state.empresaAtualLoaded = true;
      renderContent();
    }
  }

  async function handleSaveEmpresaAtual(data: EmpresaAtualUpdate): Promise<void> {
    try {
      state.empresaAtual = await updateEmpresaAtual(data);
      toast.success(t('settings.actions.empresaUpdated'));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('settings.actions.empresaUpdateError'));
      throw error;
    } finally {
      renderContent();
    }
  }

  async function handleCreateApiCredential(data: Required<ApiCredentialPayload>): Promise<void> {
    try {
      state.apiCredentials = [...state.apiCredentials, await createApiCredential(data)];
      toast.success(t('settings.actions.integrationAdded'));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('settings.actions.integrationAddError'));
      throw error;
    } finally {
      renderContent();
    }
  }

  async function handleUpdateApiCredential(id: number, data: Pick<ApiCredentialPayload, 'nome' | 'segredo'>): Promise<void> {
    try {
      const updated = await updateApiCredential(id, data);
      state.apiCredentials = state.apiCredentials.map((item) => item.id === id ? updated : item);
      toast.success(t('settings.actions.integrationUpdated'));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('settings.actions.integrationUpdateError'));
      throw error;
    } finally {
      renderContent();
    }
  }

  async function loadRegulatoryTariffs(): Promise<void> {
    try { state.regulatoryTariffStatus = await getRegulatoryTariffStatus(); state.regulatoryTariffLoadError = null; }
    catch (error) {
      state.regulatoryTariffStatus = null;
      const status = error instanceof ApiRequestError ? error.status : 0;
      state.regulatoryTariffLoadError = status === 401 || status === 403 ? 'permission'
        : status === 0 || status === 503 ? 'unavailable' : status >= 500 ? 'internal' : 'unknown';
    }
    finally { state.regulatoryTariffLoaded = true; renderContent(); }
  }

  async function handleTestApiCredential(credential: ApiCredentialRow): Promise<void> {
    try {
      const result = await testApiCredential(credential.id);
      toast.success(result.modo === 'asaas-api' ? t('settings.actions.asaasApiKeyValidated') : t('settings.actions.credentialVerifiedLocally'));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('settings.actions.credentialValidateError'));
    }
  }

  async function handleDeleteApiCredential(id: number): Promise<void> {
    try {
      await deleteApiCredential(id);
      state.apiCredentials = state.apiCredentials.filter((item) => item.id !== id);
      toast.success(t('settings.actions.integrationRemoved'));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('settings.actions.integrationRemoveError'));
    } finally {
      renderContent();
    }
  }

  return { state, actions: { loadGoogleAccounts, handleActivateAccount, handleDisconnectAccount, refreshAppearance, loadRecentLogs, loadRateioConfig, loadDriveRootFolder, handleSaveDriveRootFolderId, loadDocumentStorageProviderSetting, handleSaveDocumentStorageProvider, handleSaveRateioConfig, loadApiCredentials, loadWhatsappIntegration, handleSaveWhatsappIntegration, handleTestWhatsappIntegration, handleDeleteWhatsappIntegration, loadEmpresaAtual, handleSaveEmpresaAtual, handleCreateApiCredential, handleUpdateApiCredential, loadRegulatoryTariffs, handleTestApiCredential, handleDeleteApiCredential } };
}
