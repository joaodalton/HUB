import { apiRequest, type ApiResponse } from './apiClient';

export type CrmLead = {
  id: number;
  provider: string;
  externalId: string;
  titulo: string | null;
  status: number | null;
  valor: string | null;
  pipelineNome: string | null;
  etapaNome: string | null;
  criadoEmOrigem: string | null;
  atualizadoEmOrigem: string | null;
  importadoEm: string;
  atualizadoEm: string;
};

export type CrmSyncResumo = { totalImportados: number; totalAtualizados: number };

export async function getCrmLeads(): Promise<CrmLead[]> {
  const response = await apiRequest<ApiResponse<CrmLead[]>>('/crm-leads');
  return response.data;
}

export async function sincronizarCrmLeads(): Promise<CrmSyncResumo> {
  const response = await apiRequest<ApiResponse<{ total_importados: number; total_atualizados: number }>>('/crm-leads/sincronizar', { method: 'POST' });
  return { totalImportados: response.data.total_importados, totalAtualizados: response.data.total_atualizados };
}
