import { apiRequest } from './apiClient';
import { adjustLightness, hexToRgba } from './colorUtils';

export type AppSettings = {
  companyName: string;
  language: string;
  backgroundColor: string;
  cardColor: string;
  textColor: string;
  // Cor usada em destaque/selecao (sidebar ativo, botoes, abas ativas).
  // Chave salva no banco continua "themeColor" por compatibilidade com
  // configuracoes ja gravadas antes dessa tela ganhar os campos novos.
  accentColor: string;
  logoDataUrl: string;
};

export const DEFAULT_SETTINGS: AppSettings = {
  companyName: '',
  language: 'pt-BR',
  backgroundColor: '#0b0f19',
  cardColor: '#0f1420',
  textColor: '#f1f5f9',
  accentColor: '#f0713a',
  logoDataUrl: ''
};

type ApiResponse<T> = {
  success: boolean;
  message: string;
  data: T;
};

let cachedSettings: AppSettings = DEFAULT_SETTINGS;

export function getSettings(): AppSettings {
  return cachedSettings;
}

export async function loadSettings(): Promise<AppSettings> {
  const response = await apiRequest<ApiResponse<Record<string, string>>>('/settings');

  cachedSettings = mergeWithDefaults(response.data);
  applyAppearanceSettings();
  return cachedSettings;
}

// Aceita atualizacao parcial -- so manda pro backend as chaves que vieram,
// sem precisar reenviar o objeto inteiro (o logo, por exemplo, salva sozinho
// assim que o usuario escolhe o arquivo, sem esperar o resto do formulario).
export async function saveSettings(nextSettings: Partial<AppSettings>): Promise<AppSettings> {
  await apiRequest<ApiResponse<Record<string, string>>>('/settings', {
    method: 'PUT',
    body: toStorageKeys(nextSettings)
  });

  cachedSettings = { ...cachedSettings, ...nextSettings };
  applyAppearanceSettings();
  return cachedSettings;
}

export function resetAppearanceToDefaults(): Promise<AppSettings> {
  return saveSettings(DEFAULT_SETTINGS);
}

type ThemeColors = Pick<AppSettings, 'backgroundColor' | 'cardColor' | 'textColor' | 'accentColor'>;

// Aplica as cores como CSS custom properties em <html>, que tem prioridade
// sobre o :root do app.css. --panel-soft/--panel-hover e as variantes do
// --accent sao derivadas em vez de virarem mais color-pickers na tela.
// Exportada separada do applyAppearanceSettings() pra a tela de Aparencia
// poder usar a mesma logica no preview ao vivo (antes de salvar).
export function applyThemeVariables(theme: ThemeColors): void {
  const root = document.documentElement.style;

  root.setProperty('--bg', theme.backgroundColor);
  root.setProperty('--panel', theme.cardColor);
  root.setProperty('--panel-soft', adjustLightness(theme.cardColor, 3));
  root.setProperty('--panel-hover', adjustLightness(theme.cardColor, 5));
  root.setProperty('--text', theme.textColor);
  root.setProperty('--accent', theme.accentColor);
  root.setProperty('--accent-hover', adjustLightness(theme.accentColor, -8));
  root.setProperty('--accent-bg', hexToRgba(theme.accentColor, 0.1));
  root.setProperty('--accent-border', hexToRgba(theme.accentColor, 0.25));
}

export function applyAppearanceSettings(): void {
  applyThemeVariables(cachedSettings);
  //Nessa parte que faz a mudança do nome, tanto oq aparece do lado da logo quanto o que aparece na aba do navegador.
  document.title = cachedSettings.companyName ? `${cachedSettings.companyName} · HUB` : 'HUB';
}

function mergeWithDefaults(stored: Record<string, string>): AppSettings {
  return {
    companyName: stored.companyName ?? DEFAULT_SETTINGS.companyName,
    language: stored.language || DEFAULT_SETTINGS.language,
    backgroundColor: stored.backgroundColor || DEFAULT_SETTINGS.backgroundColor,
    cardColor: stored.cardColor || DEFAULT_SETTINGS.cardColor,
    textColor: stored.textColor || DEFAULT_SETTINGS.textColor,
    accentColor: stored.themeColor || DEFAULT_SETTINGS.accentColor,
    logoDataUrl: stored.logoDataUrl || DEFAULT_SETTINGS.logoDataUrl
  };
}

function toStorageKeys(settings: Partial<AppSettings>): Record<string, string> {
  const payload: Record<string, string> = {};

  if (settings.companyName !== undefined) payload.companyName = settings.companyName;
  if (settings.language !== undefined) payload.language = settings.language;
  if (settings.backgroundColor !== undefined) payload.backgroundColor = settings.backgroundColor;
  if (settings.cardColor !== undefined) payload.cardColor = settings.cardColor;
  if (settings.textColor !== undefined) payload.textColor = settings.textColor;
  if (settings.accentColor !== undefined) payload.themeColor = settings.accentColor;
  if (settings.logoDataUrl !== undefined) payload.logoDataUrl = settings.logoDataUrl;

  return payload;
}

export async function loadGoogleDriveRootFolderId(): Promise<string> {
  const response = await apiRequest<ApiResponse<Record<string, string>>>('/settings');
  return response.data.google_drive_root_folder_id ?? '';
}

export async function saveGoogleDriveRootFolderId(rootFolderId: string): Promise<void> {
  await apiRequest<ApiResponse<Record<string, string>>>('/settings', {
    method: 'PUT',
    body: { google_drive_root_folder_id: rootFolderId.trim() }
  });
}
