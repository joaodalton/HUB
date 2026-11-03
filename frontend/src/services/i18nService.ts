import { commonDict } from '../i18n/common';
import { navDict } from '../i18n/nav';
import { authDict } from '../i18n/auth';
import { settingsDict } from '../i18n/settings';

export type Language = 'pt' | 'en' | 'fr';

export type Translation = { pt: string; en: string; fr: string };

const STORAGE_KEY = 'hub_language';

const dictionary: Record<string, Translation> = {
  ...commonDict,
  ...navDict,
  ...authDict,
  ...settingsDict
};

function isLanguage(value: string | null): value is Language {
  return value === 'pt' || value === 'en' || value === 'fr';
}

export function getLanguage(): Language {
  const stored = window.localStorage.getItem(STORAGE_KEY);
  return isLanguage(stored) ? stored : 'pt';
}

export function setLanguage(lang: Language): void {
  window.localStorage.setItem(STORAGE_KEY, lang);
  window.dispatchEvent(new CustomEvent('languagechange'));
}

export function t(key: string): string {
  const entry = dictionary[key];
  if (!entry) return key;
  return entry[getLanguage()] || entry.pt;
}
