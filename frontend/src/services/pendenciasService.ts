import { apiRequest } from './apiClient';

export type PendenciaTipo = 'pendencia' | 'alerta' | 'erro';
export type PendenciaPrioridade = 'baixa' | 'media' | 'alta' | 'critica';
export type PendenciaStatus = 'aberta' | 'resolvida' | 'cancelada';

export const PRIORIDADES: PendenciaPrioridade[] = ['baixa', 'media', 'alta', 'critica'];

// Mesma logica do backend (models/pendencia.py): categorias comecam iguais
// pros 3 tipos, mas o mapa fica por tipo de proposito -- trocar so o valor
// de uma chave aqui no futuro, sem mexer no resto do arquivo.
const CATEGORIAS_PADRAO = ['Financeiro', 'Documentos', 'UCs', 'Usinas', 'Sistema', 'Mensagens'];
export const CATEGORIAS_POR_TIPO: Record<PendenciaTipo, string[]> = {
  pendencia: CATEGORIAS_PADRAO,
  alerta: CATEGORIAS_PADRAO,
  erro: CATEGORIAS_PADRAO
};

export type PendenciaComentario = {
  id: number;
  pendenciaId: number;
  autorId: number | null;
  autorNome: string | null;
  texto: string;
  criadoEm: string | null;
};

export type PendenciaRow = {
  id: number;
  tipo: PendenciaTipo;
  categoria: string;
  origem: string;
  titulo: string;
  descricao: string | null;
  clienteId: number | null;
  clienteNome: string | null;
  ucId: number | null;
  ucCodigo: string | null;
  usinaId: number | null;
  usinaNome: string | null;
  documentoId: number | null;
  documentoNome: string | null;
  prazo: string | null;
  prioridade: PendenciaPrioridade;
  responsavelId: number | null;
  responsavelNome: string | null;
  status: PendenciaStatus;
  metadados: Record<string, unknown> | null;
  criadoEm: string | null;
  atualizadoEm: string | null;
  resolvidoEm: string | null;
  comentarios: PendenciaComentario[];
};

export type PendenciaResumo = {
  pendencias: number;
  alertas: number;
  erros: number;
};

export type PendenciaFiltros = {
  tipo?: PendenciaTipo;
  categoria?: string;
  status?: PendenciaStatus;
};

// So os campos que a criacao manual ('+ Nova Pendencia') usa -- tipo nunca
// entra aqui, o backend sempre forca 'pendencia' pra criacao manual
// (ver pendencia_service.criar_pendencia_manual).
export type PendenciaPayload = {
  titulo: string;
  categoria: string;
  descricao: string;
  clienteId: number | null;
  ucId: number | null;
  usinaId: number | null;
  prazo: string;
  prioridade: PendenciaPrioridade;
};

type ApiResponse<T> = {
  success: boolean;
  message: string;
  data: T;
};

export async function getPendencias(filtros: PendenciaFiltros = {}): Promise<PendenciaRow[]> {
  const params = new URLSearchParams();
  if (filtros.tipo) params.set('tipo', filtros.tipo);
  if (filtros.categoria) params.set('categoria', filtros.categoria);
  if (filtros.status) params.set('status', filtros.status);

  const query = params.toString();
  const response = await apiRequest<ApiResponse<PendenciaRow[]>>(`/pendencias${query ? `?${query}` : ''}`);
  return response.data;
}

export async function getPendenciaResumo(): Promise<PendenciaResumo> {
  const response = await apiRequest<ApiResponse<PendenciaResumo>>('/pendencias/resumo');
  return response.data;
}

export async function createPendencia(data: PendenciaPayload): Promise<PendenciaRow> {
  const response = await apiRequest<ApiResponse<PendenciaRow>>('/pendencias', {
    method: 'POST',
    body: data
  });
  return response.data;
}

export async function updatePendencia(id: number, data: Partial<PendenciaPayload>): Promise<PendenciaRow> {
  const response = await apiRequest<ApiResponse<PendenciaRow>>(`/pendencias/${id}`, {
    method: 'PUT',
    body: data
  });
  return response.data;
}

export async function deletePendencia(id: number): Promise<void> {
  await apiRequest<ApiResponse<null>>(`/pendencias/${id}`, { method: 'DELETE' });
}

export async function resolverPendencia(id: number): Promise<PendenciaRow> {
  const response = await apiRequest<ApiResponse<PendenciaRow>>(`/pendencias/${id}/resolver`, { method: 'POST' });
  return response.data;
}

export async function cancelarPendencia(id: number): Promise<PendenciaRow> {
  const response = await apiRequest<ApiResponse<PendenciaRow>>(`/pendencias/${id}/cancelar`, { method: 'POST' });
  return response.data;
}

export async function reabrirPendencia(id: number): Promise<PendenciaRow> {
  const response = await apiRequest<ApiResponse<PendenciaRow>>(`/pendencias/${id}/reabrir`, { method: 'POST' });
  return response.data;
}

export async function addComentario(id: number, texto: string): Promise<PendenciaRow> {
  const response = await apiRequest<ApiResponse<PendenciaRow>>(`/pendencias/${id}/comentarios`, {
    method: 'POST',
    body: { texto }
  });
  return response.data;
}

export type VerificacaoResultado = {
  ucs_sem_usina: number;
  clientes_sem_uc: number;
  campos_faltando: number;
  documentos_faltando: number;
};

export type VerificacaoResponse = {
  verificacoes: VerificacaoResultado;
  resolvidas: number;
  total_criadas: number;
};

export async function verificarPendencias(): Promise<VerificacaoResponse> {
  const response = await apiRequest<ApiResponse<VerificacaoResponse>>('/pendencias/verificar', {
    method: 'POST'
  });
  return response.data;
}

export function tipoLabel(tipo: PendenciaTipo): string {
  if (tipo === 'alerta') return 'Alerta';
  if (tipo === 'erro') return 'Erro';
  return 'Pendência';
}

export function prioridadeLabel(prioridade: PendenciaPrioridade): string {
  const labels: Record<PendenciaPrioridade, string> = {
    baixa: 'Baixa',
    media: 'Média',
    alta: 'Alta',
    critica: 'Crítica'
  };
  return labels[prioridade];
}

export function prioridadeTone(prioridade: PendenciaPrioridade): 'neutral' | 'warning' | 'danger' {
  if (prioridade === 'critica' || prioridade === 'alta') return 'danger';
  if (prioridade === 'media') return 'warning';
  return 'neutral';
}

export function statusLabel(status: PendenciaStatus): string {
  if (status === 'resolvida') return 'Resolvida';
  if (status === 'cancelada') return 'Cancelada';
  return 'Aberta';
}

export function vinculacaoLabel(pendencia: PendenciaRow): string {
  const partes: string[] = [];
  if (pendencia.clienteNome) partes.push(`Cliente: ${pendencia.clienteNome}`);
  if (pendencia.ucCodigo) partes.push(`UC: ${pendencia.ucCodigo}`);
  if (pendencia.usinaNome) partes.push(`Usina: ${pendencia.usinaNome}`);
  if (pendencia.documentoNome) partes.push(`Documento: ${pendencia.documentoNome}`);
  return partes.length > 0 ? partes.join(' · ') : '-';
}