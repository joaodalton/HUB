export type DriveAccount = {
  id: string;
  nome: string;
  email: string;
};

export type AppSettings = {
  activeDriveAccountId: string;
  driveAccounts: DriveAccount[];
  sqlHost: string;
  sqlDatabase: string;
  themeColor: string;
  logoDataUrl: string;
};

const SETTINGS_KEY = 'hub.settings.v1';

const defaultSettings: AppSettings = {
  activeDriveAccountId: 'drive-1',
  driveAccounts: [
    { id: 'drive-1', nome: 'Conta principal', email: 'service-account@hub.local' }
  ],
  sqlHost: '',
  sqlDatabase: '',
  themeColor: '#C97A3D',
  logoDataUrl: ''
};

let settings = loadSettings();

export function getSettings(): AppSettings {
  return settings;
}

export function saveSettings(nextSettings: AppSettings): AppSettings {
  settings = nextSettings;
  window.localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  applyAppearanceSettings();
  return settings;
}

export function addDriveAccount(nome: string, email: string): AppSettings {
  const account = { id: crypto.randomUUID(), nome, email };

  return saveSettings({
    ...settings,
    activeDriveAccountId: account.id,
    driveAccounts: [...settings.driveAccounts, account]
  });
}

export function applyAppearanceSettings(): void {
  document.documentElement.style.setProperty('--copper', settings.themeColor);
}

function loadSettings(): AppSettings {
  const saved = window.localStorage.getItem(SETTINGS_KEY);

  if (!saved) return defaultSettings;

  try {
    return { ...defaultSettings, ...JSON.parse(saved) as AppSettings };
  } catch {
    return defaultSettings;
  }
}
