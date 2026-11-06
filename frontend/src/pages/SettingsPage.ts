import { createElement } from '../dom';
import { useToast } from '../hooks/useToast';
import { createBaseLayout } from '../layouts/BaseLayout';
import { applyAppearanceSettings, getSettings } from '../services/settingsService';
import { createBillingDiagnosticsPanel } from '../components/BillingDiagnosticsPanel';
import { createSettingsActions } from './settingsActions';
import { createGeralPanel } from './settingsGeneral';
import { createApiCredentialsPanel } from './settingsIntegrations';
import { createHomePanel, createLogsPanel } from './settingsLogs';
import { createDatabasePanel } from './settingsDatabase';
import { createAppearancePanel } from './settingsAppearance';
import { canManageSettings, isPlatformAdmin } from './settingsShared';
import { t } from '../services/i18nService';

type SettingsCategory = 'home' | 'geral' | 'database' | 'apis' | 'automations' | 'logs' | 'appearance' | 'administration';

type CategoryDefinition = {
  key: SettingsCategory;
  labelKey: string;
  // false = categoria so existe na navegacao, ainda sem backend por tras.
  // Mostra um aviso "em breve" em vez de fingir que a funcionalidade existe.
  ready: boolean;
};

const CATEGORIES: CategoryDefinition[] = [
  { key: 'home', labelKey: 'settings.category.home', ready: true },
  { key: 'geral', labelKey: 'settings.category.geral', ready: true },
  { key: 'database', labelKey: 'settings.category.database', ready: true },
  { key: 'apis', labelKey: 'settings.category.apis', ready: true },
  { key: 'automations', labelKey: 'settings.category.automations', ready: false },
  { key: 'logs', labelKey: 'settings.category.logs', ready: true },
  { key: 'appearance', labelKey: 'settings.category.appearance', ready: true },
  { key: 'administration', labelKey: 'settings.category.administration', ready: true }
];

export function createSettingsPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const toast = useToast();
  let activeCategory: SettingsCategory = window.location.pathname === '/integracoes' ? 'apis' : 'home';
  const { state, actions } = createSettingsActions(toast, renderContent);
  let billingDiagnosticsPanel: HTMLElement | null = null;

  renderContent();
  actions.loadGoogleAccounts();
  actions.refreshAppearance();
  actions.loadRecentLogs();
  actions.loadRateioConfig();
  actions.loadDriveRootFolder();
  actions.loadDocumentStorageProviderSetting();
  if (isPlatformAdmin()) actions.loadRegulatoryTariffs();
  else state.regulatoryTariffLoaded = true;
  if (canManageSettings()) actions.loadApiCredentials();
  else state.apiCredentialsLoaded = true;
  if (canManageSettings()) actions.loadWhatsappIntegration();
  else state.whatsappIntegrationLoaded = true;
  if (canManageSettings()) actions.loadEmpresaAtual();
  else state.empresaAtualLoaded = true;

  const layout = createBaseLayout({
    content,
    eyebrow: t('settings.eyebrow'),
    title: t('settings.title')
  });

  // So depois do createBaseLayout() acima -- e o createToastContainer() la dentro --
  // rodarem, senao toastState.container ainda ta null e showToast() nao faz nada.
  handleGoogleOAuthRedirect(toast, () => changeCategory('database'));

  return layout;

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
        return createHomePanel(state.recentLogs, state.logsLoaded, () => changeCategory('logs'));

      case 'geral':
        return createGeralPanel(
          state.empresaAtual,
          state.empresaAtualLoaded,
          state.empresaAtualLoadError,
          canManageSettings(),
          actions.loadEmpresaAtual,
          actions.handleSaveEmpresaAtual,
          state.rateioConfig,
          state.rateioConfigLoaded,
          actions.handleSaveRateioConfig
        );

      case 'database':
        return createDatabasePanel({
          storageProvider: state.documentStorageProvider,
          storageProviderLoaded: state.documentStorageProviderLoaded,
          onSaveStorageProvider: actions.handleSaveDocumentStorageProvider,
          rootFolderId: state.driveRootFolderId,
          rootFolderLoaded: state.driveRootFolderLoaded,
          canManage: canManageSettings(),
          onSaveRootFolder: actions.handleSaveDriveRootFolderId,
          regulatoryStatus: state.regulatoryTariffStatus,
          regulatoryLoaded: state.regulatoryTariffLoaded,
          regulatoryLoadError: state.regulatoryTariffLoadError,
          canManageRegulatory: isPlatformAdmin(),
          onRefreshRegulatory: actions.loadRegulatoryTariffs
        });

      case 'apis':
        return createApiCredentialsPanel(
          state.apiCredentials,
          state.apiCredentialsLoaded,
          state.apiCredentialsLoadError,
          canManageSettings(),
          actions.loadApiCredentials,
          actions.handleCreateApiCredential,
          actions.handleUpdateApiCredential,
          actions.handleTestApiCredential,
          actions.handleDeleteApiCredential,
          state.whatsappIntegration,
          state.whatsappIntegrationLoaded,
          actions.handleSaveWhatsappIntegration,
          actions.handleTestWhatsappIntegration,
          actions.handleDeleteWhatsappIntegration,
          state.googleAccounts,
          actions.handleActivateAccount,
          actions.handleDisconnectAccount
        );

      case 'logs':
        return createLogsPanel(state.recentLogs, state.logsLoaded);

      case 'appearance':
        return createAppearancePanel(getSettings(), state.appearanceLoaded, toast.success, toast.error);

      case 'administration':
        if (!isPlatformAdmin()) return createElement('p', { className: 'settings-hint', textContent: t('settings.administration.restricted') });
        billingDiagnosticsPanel ??= createBillingDiagnosticsPanel();
        return billingDiagnosticsPanel;

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
  nav.appendChild(createElement('span', { className: 'settings-category-heading', textContent: t('settings.category.heading') }));

  CATEGORIES.filter((category) => category.key !== 'administration' || isPlatformAdmin()).forEach((category) => {
    const link = createElement('button', {
      className: category.key === active ? 'settings-category-link active' : 'settings-category-link',
      type: 'button'
    });

    link.appendChild(createElement('span', { textContent: t(category.labelKey) }));
    if (!category.ready) {
      link.appendChild(createElement('span', { className: 'settings-category-tag', textContent: t('settings.category.comingSoonTag') }));
    }

    link.addEventListener('click', () => onChange(category.key));
    nav.appendChild(link);
  });

  return nav;
}

function categoryMessage(category: SettingsCategory): string {
  switch (category) {
    case 'apis':
      return t('settings.comingSoon.apis');
    case 'automations':
      return t('settings.comingSoon.automations');
    default:
      return t('settings.comingSoon.default');
  }
}

function createComingSoonPanel(message: string): HTMLElement {
  const panel = createElement('section', { className: 'placeholder-panel' });
  panel.appendChild(createElement('p', { textContent: message }));
  return panel;
}
