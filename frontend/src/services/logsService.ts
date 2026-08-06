import { apiRequest } from './apiClient';

export type LogRow = {
  id: number;
  nivel: 'info' | 'warning' | 'error';
  acao: string;
  entidade: string | null;
  entidadeId: number | null;
  mensagem: string | null;
  metadados: Record<string, unknown> | null;
  criadoEm: string | null;
};

type ApiResponse<T> = {
  success: boolean;
  message: string;
  data: T;
};

export async function getRecentLogs(limit = 50): Promise<LogRow[]> {
  const response = await apiRequest<ApiResponse<LogRow[]>>(`/logs?limit=${limit}`);
  return response.data;
}

// Timeline de um registro especifico (ex.: historico de uma Pendencia).
export async function getEntityLogs(entidade: string, entidadeId: number, limit = 50): Promise<LogRow[]> {
  const response = await apiRequest<ApiResponse<LogRow[]>>(
    `/logs?entidade=${encodeURIComponent(entidade)}&entidadeId=${entidadeId}&limit=${limit}`
  );
  return response.data;
}

export function formattedLogDate(log: LogRow): string {
  if (!log.criadoEm) return '-';
  return new Date(log.criadoEm).toLocaleString('pt-BR');
}