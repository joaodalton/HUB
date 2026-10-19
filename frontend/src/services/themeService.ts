export type ThemePreference = 'dark' | 'light' | 'system';

const STORAGE_KEY = 'hub_theme';
const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');

function isThemePreference(value: string | null): value is ThemePreference {
  return value === 'dark' || value === 'light' || value === 'system';
}

export function getThemePreference(): ThemePreference {
  const stored = window.localStorage.getItem(STORAGE_KEY);
  return isThemePreference(stored) ? stored : 'dark';
}

export function getResolvedTheme(preference = getThemePreference()): 'dark' | 'light' {
  return preference === 'system' ? (mediaQuery.matches ? 'dark' : 'light') : preference;
}

export function applyThemePreference(preference = getThemePreference()): void {
  const root = document.documentElement;
  root.dataset.theme = getResolvedTheme(preference);
  root.dataset.themePreference = preference;
  window.dispatchEvent(new Event('hub-theme-change'));
}

export function setThemePreference(preference: ThemePreference): void {
  window.localStorage.setItem(STORAGE_KEY, preference);
  applyThemePreference(preference);
}

export function initializeTheme(): void {
  applyThemePreference();
  mediaQuery.addEventListener('change', () => {
    if (getThemePreference() === 'system') applyThemePreference('system');
  });
}
