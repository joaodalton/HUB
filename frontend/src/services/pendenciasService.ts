import { apiRequest, fetchAllPages, type ApiResponse, type Pagination } from './apiClient';
import type { UserRole } from './userService';

export type PendenciaTipo = 'pendencia' | 'alerta' | 'erro';
export type PendenciaPrioridade = 'baixa' | 'media' | 'alta' | 'critica';
export type PendenciaStatus = 'aberta' | 'resolvida' | 'cancelada';
export type ResponsavelTipo = 'usuario' | 'cargo';

export const ROLES: UserRole[] = ['owner', 'admin', 'operator', 'financial', 'viewer'];

// Mesmo mapa de UsersPage.ts (roleLabel) -- duplicado de proposito pra nao
// criar dependencia cruzada entre paginas nao relacionadas.
export function roleLabel(role: UserRole): string {
  const labels: Record<UserRole, string> = {
    owner: 'Proprietário',
    admin: 'Administrador',
    operator: 'Operacional',
    financial: 'Financeiro',
    viewer: 'Visualizador'
  };
  return labels[role];
}

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
  faturaId: number | null;
  prazo: string | null;
  prioridade: PendenciaPrioridade;
  responsavelTipo: ResponsavelTipo;
  responsavelId: number | null;
  responsavelNome: string | null;
  responsavelCargo: UserRole | null;
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
  origem?: string;
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
  responsavelTipo?: ResponsavelTipo;
  responsavelId?: number | null;
  responsavelCargo?: UserRole | null;
};


function buildPendenciaQuery(filtros: PendenciaFiltros, page?: number, pageSize?: number): string {
  const params = new URLSearchParams();
  if (filtros.tipo) params.set('tipo', filtros.tipo);
  if (filtros.categoria) params.set('categoria', filtros.categoria);
  if (filtros.status) params.set('status', filtros.status);
  if (filtros.origem) params.set('origem', filtros.origem);
  if (page) params.set('page', String(page));
  if (pageSize) params.set('pageSize', String(pageSize));
  const query = params.toString();
  return query ? `?${query}` : '';
}

export type PendenciasPage = { data: PendenciaRow[]; pagination: Pagination };

export async function getPendenciasPage(filtros: PendenciaFiltros = {}, page = 1, pageSize = 50): Promise<PendenciasPage> {
  const response = await apiRequest<ApiResponse<PendenciaRow[]> & Pick<PendenciasPage, 'pagination'>>(
    `/pendencias${buildPendenciaQuery(filtros, page, pageSize)}`
  );
  return { data: response.data, pagination: response.pagination };
}

// Lista completa (todas as paginas) -- mantido pra quem precisa da fila
// inteira (dashboard, agenda, calculos), sem expor paginacao a esses
// consumidores.
export async function getPendencias(filtros: PendenciaFiltros = {}): Promise<PendenciaRow[]> {
  return fetchAllPages((page, pageSize) => getPendenciasPage(filtros, page, pageSize));
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

export function responsavelLabel(pendencia: PendenciaRow): string {
  if (pendencia.responsavelTipo === 'cargo' && pendencia.responsavelCargo) return `Cargo: ${roleLabel(pendencia.responsavelCargo)}`;
  if (pendencia.responsavelNome) return pendencia.responsavelNome;
  return '-';
}
