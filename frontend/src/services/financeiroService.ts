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

export type PendenteBoleto = {
  invoiceId: number;
  clienteId: number;
  clienteNome: string;
  ucId: number;
  ucCodigo: string;
  competencia: string;
  dataVencimento: string | null;
  valorConcessionaria: string | null;
  valorHub: string | null;
  valorCobrar: string | null;
  billingMode: 'unified' | 'separate' | null;
  emissaoPendente: boolean;
  bloqueio: { code: string; message: string } | null;
};

export type PendentesUsina = { usinaId: number | null; usinaNome: string | null; itens: PendenteBoleto[] };

export async function getPendentesBoleto(): Promise<PendentesUsina[]> {
  return (await apiRequest<ApiResponse<PendentesUsina[]>>('/financeiro/pendentes-boleto')).data;
}

export async function getFinanceiroDashboard(competencia?: string): Promise<FinanceiroDashboard> {
  const search = new URLSearchParams();
  if (competencia) search.set('competencia', competencia);
  const query = search.toString();
  const response = await apiRequest<ApiResponse<FinanceiroDashboard>>(`/financeiro/dashboard${query ? `?${query}` : ''}`);
  return response.data;
}
