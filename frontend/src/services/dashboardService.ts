import { apiRequest } from './apiClient';
import type { PendenciaPrioridade, PendenciaTipo } from './pendenciasService';

type ApiResponse<T> = {
  success: boolean;
  message: string;
  data: T;
};

export type DashboardPendencia = {
  id: number;
  titulo: string;
  tipo: PendenciaTipo;
  prioridade: PendenciaPrioridade;
  prazo: string | null;
  clienteNome: string | null;
  ucCodigo: string | null;
  usinaNome: string | null;
};

export type DashboardContagem = {
  disponivel: boolean;
  total: number | null;
  porStatus?: Record<string, number>;
  porCategoria?: Record<string, number>;
};

export type DashboardPendencias = {
  abertas: number;
  vencidas: number;
  vencendoEm7Dias: number;
  resolvidasNoMes: number;
  fila: DashboardPendencia[];
};

export type DashboardResumo = {
  geradoEm: string;
  pendencias: DashboardPendencias;
  clientes: DashboardContagem;
  ucs: DashboardContagem;
  usinas: DashboardContagem;
  documentos: DashboardContagem;
};

export async function getDashboardResumo(): Promise<DashboardResumo> {
  const response = await apiRequest<ApiResponse<DashboardResumo>>('/dashboard/resumo');
  return response.data;
}
