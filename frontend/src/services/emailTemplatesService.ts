import { apiRequest } from './apiClient';

export type EmailTemplateRow = {
  chave: string;
  nome: string;
  assunto: string;
  corpo: string;
  variaveisDisponiveis: string[];
};

type ApiResponse<T> = {
  success: boolean;
  message: string;
  data: T;
};

export async function getEmailTemplates(): Promise<EmailTemplateRow[]> {
  const response = await apiRequest<ApiResponse<EmailTemplateRow[]>>('/email-templates');
  return response.data;
}

export async function updateEmailTemplate(chave: string, assunto: string, corpo: string): Promise<EmailTemplateRow> {
  const response = await apiRequest<ApiResponse<EmailTemplateRow>>(`/email-templates/${chave}`, {
    method: 'PUT',
    body: { assunto, corpo }
  });
  return response.data;
}

export async function restoreEmailTemplate(chave: string): Promise<EmailTemplateRow> {
  const response = await apiRequest<ApiResponse<EmailTemplateRow>>(`/email-templates/${chave}/restaurar`, {
    method: 'POST'
  });
  return response.data;
}

export async function sendTestEmail(chave: string): Promise<string> {
  const response = await apiRequest<ApiResponse<null>>(`/email-templates/${chave}/testar`, {
    method: 'POST'
  });
  return response.message;
}