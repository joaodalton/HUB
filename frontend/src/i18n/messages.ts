import type { Translation } from '../services/i18nService';

export const messagesDict: Record<string, Translation> = {
  // MessagesPage.ts
  'messages.page.eyebrow': { pt: 'Automações', en: 'Automations', fr: 'Automatisations' },
  'messages.page.loadError': { pt: 'Não foi possível carregar as mensagens.', en: 'Could not load the messages.', fr: 'Impossible de charger les messages.' },
  'messages.page.conversationsTitle': { pt: 'Conversas', en: 'Conversations', fr: 'Conversations' },
  'messages.page.cancelButton': { pt: 'Cancelar', en: 'Cancel', fr: 'Annuler' },
  'messages.page.newConversationButton': { pt: 'Nova conversa', en: 'New conversation', fr: 'Nouvelle conversation' },
  'messages.page.noConversations': { pt: 'Nenhuma conversa ainda.', en: 'No conversation yet.', fr: 'Aucune conversation pour le moment.' },
  'messages.page.selectClientOption': { pt: 'Selecionar cliente (opcional)', en: 'Select a client (optional)', fr: 'Sélectionner un client (facultatif)' },
  'messages.page.phonePlaceholder': { pt: 'Telefone com DDI e DDD', en: 'Phone with country and area code', fr: "Téléphone avec indicatif pays et régional" },
  'messages.page.contactNamePlaceholder': { pt: 'Nome do contato', en: 'Contact name', fr: 'Nom du contact' },
  'messages.page.openConversationButton': { pt: 'Abrir conversa', en: 'Open conversation', fr: 'Ouvrir la conversation' },
  'messages.page.openConversationError': { pt: 'Não foi possível abrir a conversa.', en: 'Could not open the conversation.', fr: "Impossible d'ouvrir la conversation." },
  'messages.page.selectConversationPrompt': { pt: 'Selecione ou crie uma conversa para ver o histórico.', en: 'Select or create a conversation to view the history.', fr: "Sélectionnez ou créez une conversation pour voir l'historique." },
  'messages.page.emptyMessageBody': { pt: '(mensagem sem texto)', en: '(message without text)', fr: '(message sans texte)' },
  'messages.page.messagePlaceholder': { pt: 'Digite uma mensagem', en: 'Type a message', fr: 'Saisissez un message' },
  'messages.page.sendButton': { pt: 'Enviar', en: 'Send', fr: 'Envoyer' },
  'messages.page.sendError': { pt: 'Não foi possível enviar a mensagem.', en: 'Could not send the message.', fr: "Impossible d'envoyer le message." },
  'messages.page.loadHistoryError': { pt: 'Não foi possível carregar o histórico.', en: 'Could not load the history.', fr: "Impossible de charger l'historique." },
  'messages.page.now': { pt: 'agora', en: 'now', fr: 'maintenant' }
};
