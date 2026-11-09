import { commonDict } from '../i18n/common';
import { navDict } from '../i18n/nav';
import { authDict } from '../i18n/auth';
import { settingsDict } from '../i18n/settings';
import { sharedDict } from '../i18n/shared';
import { dashboardDict } from '../i18n/dashboard';
import { clientsDict } from '../i18n/clients';
import { ucsDict } from '../i18n/ucs';
import { plantsDict } from '../i18n/plants';
import { rateioDict } from '../i18n/rateio';
import { rateioFormularioDict } from '../i18n/rateioFormulario';
import { faturasDict } from '../i18n/faturas';
import { billingDict } from '../i18n/billing';
import { pendenciasDict } from '../i18n/pendencias';
import { agendaDict } from '../i18n/agenda';
import { documentsDict } from '../i18n/documents';
import { empresasDict } from '../i18n/empresas';
import { usersDict } from '../i18n/users';
import { templatesDict } from '../i18n/templates';
import { reportsDict } from '../i18n/reports';
import { messagesDict } from '../i18n/messages';
import { platformDict } from '../i18n/platform';
import { crmLeadsDict } from '../i18n/crmLeads';

export type Language = 'pt' | 'en' | 'fr';

export type Translation = { pt: string; en: string; fr: string };

const STORAGE_KEY = 'hub_language';

const dictionary: Record<string, Translation> = {
  ...commonDict,
  ...navDict,
  ...authDict,
  ...settingsDict,
  ...sharedDict,
  ...dashboardDict,
  ...clientsDict,
  ...ucsDict,
  ...plantsDict,
  ...rateioDict,
  ...rateioFormularioDict,
  ...faturasDict,
  ...billingDict,
  ...pendenciasDict,
  ...agendaDict,
  ...documentsDict,
  ...empresasDict,
  ...usersDict,
  ...templatesDict,
  ...reportsDict,
  ...messagesDict,
  ...platformDict,
  ...crmLeadsDict
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
