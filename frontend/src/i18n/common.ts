import type { Translation } from '../services/i18nService';

export const commonDict: Record<string, Translation> = {
  'common.save': { pt: 'Salvar', en: 'Save', fr: 'Enregistrer' },
  'common.saving': { pt: 'Salvando...', en: 'Saving...', fr: 'Enregistrement...' },
  'common.cancel': { pt: 'Cancelar', en: 'Cancel', fr: 'Annuler' },
  'common.retry': { pt: 'Tentar novamente', en: 'Try again', fr: 'Réessayer' },
  'common.loading': { pt: 'Carregando...', en: 'Loading...', fr: 'Chargement...' },
  'common.remove': { pt: 'Remover', en: 'Remove', fr: 'Supprimer' },
  'common.restoreDefault': { pt: 'Restaurar padrão', en: 'Restore default', fr: 'Restaurer par défaut' }
};
