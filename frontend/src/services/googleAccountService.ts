import { config } from './config';
import { apiRequest } from './apiClient';

export type GoogleAccountRow = {
  id: number;
  nome: string;
  email: string;
  scopes: string[];
  ativa: boolean;
};

type ApiResponse<T> = {
  success: boolean;
  message: string;
  data: T;
};

export async function getGoogleAccounts(): Promise<GoogleAccountRow[]> {
  const response = await apiRequest<ApiResponse<GoogleAccountRow[]>>('/oauth/google/accounts');
  return response.data;
}

export async function activateGoogleAccount(id: number): Promise<GoogleAccountRow> {
  const response = await apiRequest<ApiResponse<GoogleAccountRow>>(`/oauth/google/accounts/${id}/activate`, {
    method: 'POST'
  });
  return response.data;
}

export async function disconnectGoogleAccount(id: number): Promise<void> {
  await apiRequest<ApiResponse<null>>(`/oauth/google/accounts/${id}`, { method: 'DELETE' });
}

// Navegacao direta (nao fetch) -- o backend redireciona pra tela de consentimento do Google.
export function getGoogleAuthorizeUrl(): string {
  return `${config.apiBaseUrl}${config.apiPrefix}/oauth/google/authorize`;
}
