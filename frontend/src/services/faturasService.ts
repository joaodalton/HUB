// frontend/src/services/faturasService.ts
import { apiRequest } from './apiClient';

export type FaturaStatus = 'pendente' | 'pago' | 'vencido' | 'cancelado';

export type FaturaRow = {
  id: number;
  clienteId: number;
  clienteNome: string | null;
  ucId: number | null;
  ucCodigo: string | null;
  competencia: string;
  valorOriginal: number | null;
  descontoPercentual: number | null;
  valorCobrado: number;
  vencimento: string;
  status: FaturaStatus;
  formaPagamento: string | null;
  linkPagamento: string | null;
  dataPagamento: string | null;
  criadoEm: string | null;
};

export type FaturaPayload = {
  clienteId: number;
  ucId?: number | null;
  competencia: string;
  valorOriginal?: number | null;
  descontoPercentual?: number | null;
  valorCobrado: number;
  vencimento: string;
  formaPagamento?: string;
};

type ApiResponse<T> = {
  success: boolean;
  message: string;
  data: T;
};

export async function getFaturas(filtros: { clienteId?: number; status?: FaturaStatus } = {}): Promise<FaturaRow[]> {
  const params = new URLSearchParams();
  if (filtros.clienteId) params.set('clienteId', String(filtros.clienteId));
  if (filtros.status) params.set('status', filtros.status);

  const query = params.toString();
  const response = await apiRequest<ApiResponse<FaturaRow[]>>(`/faturas${query ? `?${query}` : ''}`);
  return response.data;
}

export async function createFatura(data: FaturaPayload): Promise<FaturaRow> {
  const response = await apiRequest<ApiResponse<FaturaRow>>('/faturas', {
    method: 'POST',
    body: data
  });
  return response.data;
}

export async function cancelarFatura(id: number): Promise<FaturaRow> {
  const response = await apiRequest<ApiResponse<FaturaRow>>(`/faturas/${id}/cancelar`, { method: 'POST' });
  return response.data;
}

export function statusLabel(status: FaturaStatus): string {
  const labels: Record<FaturaStatus, string> = {
    pendente: 'Pendente',
    pago: 'Pago',
    vencido: 'Vencido',
    cancelado: 'Cancelado'
  };
  return labels[status];
}

export function statusTone(status: FaturaStatus): 'success' | 'warning' | 'danger' | 'neutral' {
  if (status === 'pago') return 'success';
  if (status === 'vencido') return 'danger';
  if (status === 'cancelado') return 'neutral';
  return 'warning';
}
