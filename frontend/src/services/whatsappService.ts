import { apiRequest } from './apiClient';

type ApiResponse<T> = { success: boolean; message: string; data: T };

export type WhatsappIntegration = {
  id: number; phoneNumberId: string; businessAccountId: string; displayPhoneNumber: string | null;
  verifiedName: string | null; enabled: boolean; configured: boolean; updatedAt: string | null;
};
export type WhatsappIntegrationInput = {
  phoneNumberId: string; businessAccountId: string; displayPhoneNumber?: string; accessToken?: string; enabled?: boolean;
};
export type WhatsappMessage = {
  id: number; conversationId: number; templateId: number | null; direction: 'inbound' | 'outbound';
  type: string; body: string; status: string; providerError: string | null; sentAt: string | null; createdAt: string | null;
};
export type WhatsappConversation = {
  id: number; clientId: number | null; clientName: string | null; consumerUnitId: number | null;
  consumerUnitCode: string | null; phoneNumber: string; contactName: string | null;
  lastMessageAt: string | null; unreadCount: number; lastMessage: WhatsappMessage | null;
};

export async function getWhatsappIntegration(): Promise<WhatsappIntegration | null> {
  return (await apiRequest<ApiResponse<WhatsappIntegration | null>>('/whatsapp/integracao')).data;
}
export async function saveWhatsappIntegration(input: WhatsappIntegrationInput): Promise<WhatsappIntegration> {
  return (await apiRequest<ApiResponse<WhatsappIntegration>>('/whatsapp/integracao', { method: 'PUT', body: input })).data;
}
export async function testWhatsappIntegration(): Promise<WhatsappIntegration> {
  return (await apiRequest<ApiResponse<WhatsappIntegration>>('/whatsapp/integracao/testar', { method: 'POST' })).data;
}
export async function deleteWhatsappIntegration(): Promise<void> {
  await apiRequest<ApiResponse<null>>('/whatsapp/integracao', { method: 'DELETE' });
}
export async function getWhatsappConversations(): Promise<WhatsappConversation[]> {
  return (await apiRequest<ApiResponse<WhatsappConversation[]>>('/whatsapp/conversas')).data;
}
export async function createWhatsappConversation(input: { clientId?: number; consumerUnitId?: number; phoneNumber?: string; contactName?: string }): Promise<WhatsappConversation> {
  return (await apiRequest<ApiResponse<WhatsappConversation>>('/whatsapp/conversas', { method: 'POST', body: input })).data;
}
export async function getWhatsappMessages(conversationId: number): Promise<WhatsappMessage[]> {
  return (await apiRequest<ApiResponse<WhatsappMessage[]>>(`/whatsapp/conversas/${conversationId}/mensagens`)).data;
}
export async function sendWhatsappText(conversationId: number, body: string): Promise<WhatsappMessage> {
  return (await apiRequest<ApiResponse<WhatsappMessage>>(`/whatsapp/conversas/${conversationId}/mensagens`, { method: 'POST', body: { body } })).data;
}
export async function submitWhatsappTemplate(templateId: number) {
  return (await apiRequest<ApiResponse<unknown>>(`/whatsapp/templates/${templateId}/submeter`, { method: 'POST' })).data;
}
export async function syncWhatsappTemplates() {
  return (await apiRequest<ApiResponse<unknown>>('/whatsapp/templates/sincronizar', { method: 'POST' })).data;
}
