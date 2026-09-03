import { apiRequest } from './apiClient';

type ApiResponse<T> = { success: boolean; message: string; data: T };

export type FaturaStatus = 'pending' | 'received' | 'overdue' | 'canceled' | 'refunded';

export type FaturaRow = {
  id: number;
  clienteId: number;
  clienteNome: string;
  ucId: number;
  ucCodigo: string;
  concessionaria: string | null;
  competencia: string;
  valor: string | number;
  mesVencimento: string;
  origem: 'manual' | 'automatica';
  asaasId: string;
  asaasStatus: FaturaStatus;
  boletoUrl: string | null;
  linhaDigitavel: string | null;
  codigoBarras: string | null;
  enviadoEm: string | null;
  criadoEm: string | null;
};

export type FaturaPayload = {
  clienteId: number;
  ucId: number;
  valor: number;
  mesVencimento: string;
  competencia: string;
};

export type FaturasResumo = Partial<Record<FaturaStatus, number>>;

export async function getFaturas(filters: { clienteId?: number; ucId?: number; status?: FaturaStatus; competencia?: string } = {}): Promise<FaturaRow[]> {
  const search = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => { if (value !== undefined) search.set(key, String(value)); });
  const response = await apiRequest<ApiResponse<FaturaRow[]>>(`/faturas${search.size ? `?${search}` : ''}`);
  return response.data;
}

export async function getFaturasResumo(): Promise<FaturasResumo> {
  const response = await apiRequest<ApiResponse<FaturasResumo>>('/faturas/resumo');
  return response.data;
}

export async function createFatura(data: FaturaPayload): Promise<FaturaRow> {
  const response = await apiRequest<ApiResponse<FaturaRow>>('/faturas', { method: 'POST', body: data });
  return response.data;
}

export async function syncFatura(id: number): Promise<FaturaRow> {
  const response = await apiRequest<ApiResponse<FaturaRow>>(`/faturas/${id}/sincronizar`, { method: 'POST' });
  return response.data;
}

export async function cancelFatura(id: number): Promise<FaturaRow> {
  const response = await apiRequest<ApiResponse<FaturaRow>>(`/faturas/${id}/cancelar`, { method: 'POST' });
  return response.data;
}
