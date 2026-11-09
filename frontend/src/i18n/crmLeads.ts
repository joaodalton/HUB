import type { Translation } from '../services/i18nService';

export const crmLeadsDict: Record<string, Translation> = {
  'crmLeads.page.eyebrow': { pt: 'Integrações', en: 'Integrations', fr: 'Intégrations' },
  'crmLeads.page.title': { pt: 'Leads importados do CRM', en: 'Leads imported from CRM', fr: 'Leads importés du CRM' },
  'crmLeads.page.syncButton': { pt: 'Sincronizar agora', en: 'Sync now', fr: 'Synchroniser maintenant' },
  'crmLeads.page.syncSuccess': { pt: 'Sincronização concluída: {imported} importado(s), {updated} atualizado(s).', en: 'Sync complete: {imported} imported, {updated} updated.', fr: 'Synchronisation terminée : {imported} importé(s), {updated} mis à jour.' },
  'crmLeads.page.syncError': { pt: 'Não foi possível sincronizar com o PipeRun.', en: 'Could not sync with PipeRun.', fr: 'Impossible de synchroniser avec PipeRun.' },
  'crmLeads.page.loadError': { pt: 'Não foi possível carregar os leads importados.', en: 'Could not load imported leads.', fr: 'Impossible de charger les leads importés.' },
  'crmLeads.page.empty': { pt: 'Nenhum lead importado ainda. Configure a credencial do PipeRun em Configurações > Integrações e sincronize.', en: 'No leads imported yet. Configure the PipeRun credential in Settings > Integrations and sync.', fr: 'Aucun lead importé encore. Configurez la credential PipeRun dans Paramètres > Intégrations et synchronisez.' },
  'crmLeads.page.tableTitle': { pt: 'Leads', en: 'Leads', fr: 'Leads' },
  'crmLeads.page.colTitulo': { pt: 'Negócio', en: 'Deal', fr: 'Affaire' },
  'crmLeads.page.colPipeline': { pt: 'Pipeline', en: 'Pipeline', fr: 'Pipeline' },
  'crmLeads.page.colEtapa': { pt: 'Etapa', en: 'Stage', fr: 'Étape' },
  'crmLeads.page.colValor': { pt: 'Valor', en: 'Value', fr: 'Valeur' },
  'crmLeads.page.colStatus': { pt: 'Status', en: 'Status', fr: 'Statut' },
  'crmLeads.page.colImportadoEm': { pt: 'Importado em', en: 'Imported at', fr: 'Importé le' },
  'crmLeads.page.statusAberta': { pt: 'Aberta', en: 'Open', fr: 'Ouverte' },
  'crmLeads.page.statusGanha': { pt: 'Ganha', en: 'Won', fr: 'Gagnée' },
  'crmLeads.page.statusPerdida': { pt: 'Perdida', en: 'Lost', fr: 'Perdue' }
};
