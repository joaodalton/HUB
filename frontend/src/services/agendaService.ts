import { apiRequest } from './apiClient';
import type { PendenciaPrioridade, PendenciaStatus, PendenciaTipo } from './pendenciasService';

type ApiResponse<T> = { success: boolean; message: string; data: T };

export type AgendaModo = 'dia' | 'semana' | 'mes';

/** Projection of a pending task. Agenda never owns a second copy of the data. */
export type AgendaItem = {
  fonte: 'pendencia';
  pendenciaId: number;
  id: number;
  titulo: string;
  tipo: PendenciaTipo;
  categoria: string;
  origem: string;
  prioridade: PendenciaPrioridade;
  status: PendenciaStatus;
  prazo: string;
  clienteId: number | null;
  ucId: number | null;
  usinaId: number | null;
  documentoId: number | null;
};

export type AgendaResultado = { itens: AgendaItem[] };

/** The API applies tenant isolation and returns only items within the inclusive range. */
export async function getAgenda(inicio: string, fim: string, visao: AgendaModo): Promise<AgendaResultado> {
  const query = new URLSearchParams({ inicio, fim, visao });
  const response = await apiRequest<ApiResponse<AgendaResultado>>(`/agenda?${query.toString()}`);
  return response.data;
}
