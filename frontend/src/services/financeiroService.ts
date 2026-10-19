import { apiRequest, type ApiResponse } from './apiClient';

export type FinanceiroDashboardCliente = {
  clienteId: number;
  clienteNome: string;
  recebido: string;
  pendente: string;
};

export type FinanceiroDashboardUsina = {
  usinaId: number;
  usinaNome: string;
  recebido: string;
  repasseCalculado: string | null;
  contratoPendente: boolean;
  /** Presente (true) apenas quando a usina nao tem nenhuma UC conectada; ausente no caso normal. */
  semClientesConectados?: boolean;
  /** Presente (true) apenas quando o contrato esta configurado mas nem todas as UCs pagaram ainda. */
  aguardandoPagamentos?: boolean;
};

export type FinanceiroDashboard = {
  porCliente: FinanceiroDashboardCliente[];
  porUsina: FinanceiroDashboardUsina[];
};

export async function getFinanceiroDashboard(competencia?: string): Promise<FinanceiroDashboard> {
  const search = new URLSearchParams();
  if (competencia) search.set('competencia', competencia);
  const query = search.toString();
  const response = await apiRequest<ApiResponse<FinanceiroDashboard>>(`/financeiro/dashboard${query ? `?${query}` : ''}`);
  return response.data;
}
