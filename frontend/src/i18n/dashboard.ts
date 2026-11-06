import type { Translation } from '../services/i18nService';

export const dashboardDict: Record<string, Translation> = {
  // DashboardPage.ts
  'dashboard.eyebrow': { pt: 'Dashboard', en: 'Dashboard', fr: 'Tableau de bord' },
  'dashboard.title': { pt: 'Visão operacional da sua empresa', en: "Operational view of your company", fr: 'Vue opérationnelle de votre entreprise' },
  'dashboard.loadError.title': { pt: 'Não foi possível carregar o dashboard.', en: 'Could not load the dashboard.', fr: 'Impossible de charger le tableau de bord.' },
  'dashboard.loadError.description': { pt: 'Verifique sua conexão e tente novamente.', en: 'Check your connection and try again.', fr: 'Vérifiez votre connexion et réessayez.' },
  'dashboard.metric.pendingOpen': { pt: 'Pendências abertas', en: 'Open pending items', fr: 'Tâches ouvertes' },
  'dashboard.metric.pendingOverdue': { pt: 'Pendências vencidas', en: 'Overdue pending items', fr: 'Tâches en retard' },
  'dashboard.metric.dueIn7Days': { pt: 'Vencem em 7 dias', en: 'Due in 7 days', fr: 'Échéance dans 7 jours' },
  'dashboard.metric.resolvedThisMonth': { pt: 'Concluídas no mês', en: 'Completed this month', fr: 'Terminées ce mois-ci' },
  'dashboard.entity.clients': { pt: 'Clientes', en: 'Clients', fr: 'Clients' },
  'dashboard.entity.ucs': { pt: 'UCs', en: 'Units', fr: 'Unités' },
  'dashboard.entity.plants': { pt: 'Usinas', en: 'Plants', fr: 'Centrales' },
  'dashboard.entity.documents': { pt: 'Documentos', en: 'Documents', fr: 'Documents' },
  'dashboard.updatedAt': { pt: 'Atualizado', en: 'Updated', fr: 'Mis à jour' },
  'dashboard.operation': { pt: 'Operação', en: 'Operation', fr: 'Opération' },
  'dashboard.registrations': { pt: 'Cadastros', en: 'Registrations', fr: 'Enregistrements' },
  'dashboard.viewAll': { pt: 'Ver todas', en: 'View all', fr: 'Voir tout' },
  'dashboard.priority': { pt: 'Prioridade', en: 'Priority', fr: 'Priorité' },
  'dashboard.queueTitle': { pt: 'Fila operacional', en: 'Operational queue', fr: "File d'attente opérationnelle" },
  'dashboard.queueEmpty': { pt: 'Nenhuma pendência aberta no momento.', en: 'No open pending items at the moment.', fr: "Aucune tâche ouverte pour le moment." },
  'dashboard.context.client': { pt: 'Cliente', en: 'Client', fr: 'Client' },
  'dashboard.context.uc': { pt: 'UC', en: 'Unit', fr: 'Unité' },
  'dashboard.context.plant': { pt: 'Usina', en: 'Plant', fr: 'Centrale' },
  'dashboard.context.none': { pt: 'Sem vínculo cadastrado', en: 'No linked record', fr: "Aucun lien enregistré" },
  'dashboard.deadline': { pt: 'Prazo', en: 'Deadline', fr: 'Échéance' },
  'dashboard.noDeadline': { pt: 'Sem prazo', en: 'No deadline', fr: "Pas d'échéance" }
};
