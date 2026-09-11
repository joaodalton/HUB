import { apiRequest } from './apiClient';
import type { PendenciaPrioridade, PendenciaStatus, PendenciaTipo } from './pendenciasService';

type ApiResponse<T> = { success: boolean; message: string; data: T };

export type AgendaModo = 'dia' | 'semana' | 'mes';

export type AgendaFonte = 'pendencia' | 'evento';

/** Pendências são projeções; eventos pertencem exclusivamente à Agenda. */
export type AgendaItem = {
  fonte: AgendaFonte;
  pendenciaId: number | null;
  eventoId: number | null;
  id: number;
  titulo: string;
  descricao: string | null;
  tipo: PendenciaTipo | 'evento';
  categoria: string;
  origem: string;
  prioridade: PendenciaPrioridade;
  status: PendenciaStatus;
  prazo: string;
  fim: string | null;
  clienteId: number | null;
  ucId: number | null;
  usinaId: number | null;
  documentoId: number | null;
};

export type AgendaResultado = { itens: AgendaItem[] };
export type AgendaEventoPayload = { titulo: string; descricao?: string; inicio: string; fim?: string | null; categoria?: string };

/** The API applies tenant isolation and returns only items within the inclusive range. */
export async function getAgenda(inicio: string, fim: string, visao: AgendaModo): Promise<AgendaResultado> {
  const query = new URLSearchParams({ inicio, fim, visao });
  const response = await apiRequest<ApiResponse<AgendaResultado>>(`/agenda?${query.toString()}`);
  return response.data;
}

export async function createAgendaEvento(data: AgendaEventoPayload): Promise<AgendaItem> {
  const response = await apiRequest<ApiResponse<AgendaItem>>('/agenda/eventos', { method: 'POST', body: data });
  return response.data;
}

export async function updateAgendaEvento(id: number, data: AgendaEventoPayload): Promise<AgendaItem> {
  const response = await apiRequest<ApiResponse<AgendaItem>>(`/agenda/eventos/${id}`, { method: 'PUT', body: data });
  return response.data;
}

export async function cancelAgendaEvento(id: number): Promise<void> {
  await apiRequest<ApiResponse<null>>(`/agenda/eventos/${id}`, { method: 'DELETE' });
}
