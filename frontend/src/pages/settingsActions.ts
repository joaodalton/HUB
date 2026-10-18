import { getEmpresaAtual, updateEmpresaAtual, type EmpresaAtual, type EmpresaAtualUpdate } from '../services/empresaService';
import { loadSettings, loadGoogleDriveRootFolderId, saveGoogleDriveRootFolderId } from '../services/settingsService';
import { activateGoogleAccount, disconnectGoogleAccount, getGoogleAccounts, type GoogleAccountRow } from '../services/googleAccountService';
import { getRecentLogs, type LogRow } from '../services/logsService';
import { DEFAULT_RATEIO_CONFIG, getRateioConfig, saveRateioConfig, type RateioConfig } from '../services/rateioConfigService';
import { createApiCredential, deleteApiCredential, getApiCredentials, testApiCredential, updateApiCredential, type ApiCredentialPayload, type ApiCredentialRow } from '../services/apiCredentialsService';
import { deleteWhatsappIntegration, getWhatsappIntegration, saveWhatsappIntegration, testWhatsappIntegration, type WhatsappIntegration, type WhatsappIntegrationInput } from '../services/whatsappService';
import { getRegulatoryTariffStatus, type RegulatoryTariffStatus } from '../services/regulatoryTariffsService';
import { ApiRequestError } from '../services/apiClient';

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
      toast.success('Pasta raiz do Google Drive salva.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Nao foi possivel salvar a pasta raiz do Google Drive.');
      throw error;
    } finally {
      renderContent();
    }
  }

  async function handleSaveRateioConfig(novoConfig: RateioConfig): Promise<void> {
    try {
      state.rateioConfig = await saveRateioConfig(novoConfig);
      toast.success('Configuração salva.');
    } catch {
      toast.error('Não foi possível salvar a configuração.');
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
    try { state.whatsappIntegration = await saveWhatsappIntegration(input); toast.success('WhatsApp Meta Cloud API configurado.'); }
    catch (error) { toast.error(error instanceof Error ? error.message : 'Não foi possível salvar a integração WhatsApp.'); throw error; }
    finally { renderContent(); }
  }

  async function handleTestWhatsappIntegration(): Promise<void> {
    try { state.whatsappIntegration = await testWhatsappIntegration(); toast.success('Conexão com a Meta confirmada.'); }
    catch (error) { toast.error(error instanceof Error ? error.message : 'A Meta não confirmou a conexão.'); }
    finally { renderContent(); }
  }

  async function handleDeleteWhatsappIntegration(): Promise<void> {
    if (!window.confirm('Remover a integração WhatsApp desta empresa? O histórico de mensagens será preservado.')) return;
    try { await deleteWhatsappIntegration(); state.whatsappIntegration = null; toast.success('Integração WhatsApp removida.'); }
    catch (error) { toast.error(error instanceof Error ? error.message : 'Não foi possível remover a integração.'); }
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
      state.apiCredentials = [...state.apiCredentials, await createApiCredential(data)];
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
      state.apiCredentials = state.apiCredentials.map((item) => item.id === id ? updated : item);
      toast.success('Integração atualizada.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Não foi possível atualizar a integração.');
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
      toast.success(result.modo === 'asaas-api' ? 'Chave de API Asaas validada.' : 'Credencial verificada localmente.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Não foi possível validar a credencial.');
    }
  }

  async function handleDeleteApiCredential(id: number): Promise<void> {
    try {
      await deleteApiCredential(id);
      state.apiCredentials = state.apiCredentials.filter((item) => item.id !== id);
      toast.success('Integração removida.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Não foi possível remover a integração.');
    } finally {
      renderContent();
    }
  }

  return { state, actions: { loadGoogleAccounts, handleActivateAccount, handleDisconnectAccount, refreshAppearance, loadRecentLogs, loadRateioConfig, loadDriveRootFolder, handleSaveDriveRootFolderId, handleSaveRateioConfig, loadApiCredentials, loadWhatsappIntegration, handleSaveWhatsappIntegration, handleTestWhatsappIntegration, handleDeleteWhatsappIntegration, loadEmpresaAtual, handleSaveEmpresaAtual, handleCreateApiCredential, handleUpdateApiCredential, loadRegulatoryTariffs, handleTestApiCredential, handleDeleteApiCredential } };
}
