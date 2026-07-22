import { apiRequest } from './apiClient';

export type AppSettings = {
  themeColor: string;
  logoDataUrl: string;
};

const DEFAULT_SETTINGS: AppSettings = {
  themeColor: '#C97A3D',
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

  cachedSettings = {
    themeColor: response.data.themeColor || DEFAULT_SETTINGS.themeColor,
    logoDataUrl: response.data.logoDataUrl || DEFAULT_SETTINGS.logoDataUrl
  };
  applyAppearanceSettings();
  return cachedSettings;
}

export async function saveSettings(nextSettings: AppSettings): Promise<AppSettings> {
  await apiRequest<ApiResponse<Record<string, string>>>('/settings', {
    method: 'PUT',
    body: nextSettings
  });

  cachedSettings = nextSettings;
  applyAppearanceSettings();
  return cachedSettings;
}

export function applyAppearanceSettings(): void {
  document.documentElement.style.setProperty('--copper', cachedSettings.themeColor);
}