import { apiRequest } from './apiClient';

type ApiResponse<T> = { success: boolean; message: string; data: T };

export type ApiCredentialProvider = 'resend' | 'whatsapp' | 'asaas' | 'concessionaria';

/** Metadata only. The API deliberately never returns the configured secret. */
export type ApiCredentialRow = {
  id: number;
  provider: ApiCredentialProvider;
  nome: string;
  configurada: boolean;
  criadaEm?: string;
  atualizadaEm?: string;
};

export type ApiCredentialPayload = {
  provider: ApiCredentialProvider;
  nome: string;
  segredo?: string;
};

export type ApiCredentialUpdatePayload = Pick<ApiCredentialPayload, 'nome' | 'segredo'>;

export async function getApiCredentials(): Promise<ApiCredentialRow[]> {
  const response = await apiRequest<ApiResponse<ApiCredentialRow[]>>('/api-credentials');
  return response.data;
}

export async function createApiCredential(data: Required<ApiCredentialPayload>): Promise<ApiCredentialRow> {
  const response = await apiRequest<ApiResponse<ApiCredentialRow>>('/api-credentials', { method: 'POST', body: data });
  return response.data;
}

export async function updateApiCredential(id: number, data: ApiCredentialUpdatePayload): Promise<ApiCredentialRow> {
  const response = await apiRequest<ApiResponse<ApiCredentialRow>>(`/api-credentials/${id}`, { method: 'PUT', body: data });
  return response.data;
}

export async function deleteApiCredential(id: number): Promise<void> {
  await apiRequest<ApiResponse<null>>(`/api-credentials/${id}`, { method: 'DELETE' });
}
