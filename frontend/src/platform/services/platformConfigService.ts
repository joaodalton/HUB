import { apiRequest, type ApiResponse } from '../../services/apiClient';

export type PlatformConfiguracao = {
  asaasApiBaseUrl: string | null;
  asaasApiKeyConfigurada: boolean;
  asaasWebhookTokenConfigurada: boolean;
  signupCodeConfigurada: boolean;
  signupEmpresaId: number | null;
};

export type PlatformConfiguracaoPayload = Partial<{
  asaasApiBaseUrl: string;
  asaasApiKey: string;
  asaasWebhookToken: string;
  signupCode: string;
  signupEmpresaId: number | null;
}>;

export async function getPlatformConfiguracao(): Promise<PlatformConfiguracao> {
  const response = await apiRequest<ApiResponse<PlatformConfiguracao>>('/platform/configuracao');
  return response.data;
}

export async function updatePlatformConfiguracao(payload: PlatformConfiguracaoPayload): Promise<PlatformConfiguracao> {
  const response = await apiRequest<ApiResponse<PlatformConfiguracao>>('/platform/configuracao', {
    method: 'PUT',
    body: payload
  });
  return response.data;
}
