import { apiRequest } from './apiClient';

export type TemplateCanal = 'email' | 'whatsapp';

export type MessageTemplateRow = {
  id: number;
  nome: string;
  canal: TemplateCanal;
  assunto?: string | null;
  corpo: string;
  chave: string;
  variaveisPermitidas: string[];
  padrao: boolean;
};

type ApiResponse<T> = { success: boolean; message: string; data: T };

export type MessageTemplateInput = {
  nome: string;
  canal: TemplateCanal;
  chave?: string;
  assunto?: string;
  corpo: string;
  variaveisPermitidas?: string[];
};

export async function getMessageTemplates(canal?: TemplateCanal): Promise<MessageTemplateRow[]> {
  const query = canal ? `?canal=${encodeURIComponent(canal)}` : '';
  const response = await apiRequest<ApiResponse<MessageTemplateRow[]>>(`/message-templates${query}`);
  return response.data;
}

export async function createMessageTemplate(input: MessageTemplateInput): Promise<MessageTemplateRow> {
  const response = await apiRequest<ApiResponse<MessageTemplateRow>>('/message-templates', { method: 'POST', body: input });
  return response.data;
}

export async function updateMessageTemplate(id: number, input: MessageTemplateInput): Promise<MessageTemplateRow> {
  const response = await apiRequest<ApiResponse<MessageTemplateRow>>(`/message-templates/${id}`, { method: 'PUT', body: input });
  return response.data;
}

export async function deleteMessageTemplate(id: number): Promise<void> {
  await apiRequest<ApiResponse<null>>(`/message-templates/${id}`, { method: 'DELETE' });
}

export async function restoreMessageTemplate(id: number): Promise<MessageTemplateRow> {
  const response = await apiRequest<ApiResponse<MessageTemplateRow>>(`/message-templates/${id}/restaurar`, { method: 'POST' });
  return response.data;
}
