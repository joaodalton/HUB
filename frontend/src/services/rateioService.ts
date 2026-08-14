// frontend/src/services/rateioService.ts
import { apiRequest } from './apiClient';

export type RateioUcResultado = {
  ucId: number;
  ucCodigo: string;
  clienteNome: string | null;
  clienteCpfCnpj: string | null;
  consumoTotal: number;
  consumoConsiderado: number;
  bufferPercentualAplicado: number;
  consumoAjustado: number;
  producaoConsiderada: number;
  percentualCalculado: number;
  qualificado: boolean;
  motivoQualificacao: string;
};

export type RateioPreview = {
  plantId: number;
  plantNome: string;
  producaoMedia: number;
  reservaPercentual: number;
  producaoDisponivel: number;
  isCoringa: boolean;
  percentualTotalAlocado: number;
  excedeLimite: boolean;
  ucs: RateioUcResultado[];
  warnings: string[];
};

type ApiResponse<T> = {
  success: boolean;
  message: string;
  data: T;
};

export async function previewRateio(plantId: number): Promise<RateioPreview> {
  const response = await apiRequest<ApiResponse<RateioPreview[]>>(`/rateio/preview?plantId=${plantId}`);
  // Backend sempre devolve array (suporta calcular várias usinas de uma vez) --
  // aqui a gente sempre filtra por 1 plantId, então é sempre o primeiro item.
  return response.data[0];
}

export async function aplicarRateio(competencia: string, plantId: number): Promise<RateioPreview[]> {
  const response = await apiRequest<ApiResponse<RateioPreview[]>>('/rateio/aplicar', {
    method: 'POST',
    body: { competencia, plantId }
  });
  return response.data;
}

export type RateioQualificacaoUc = {
  ucId: number;
  ucCodigo: string;
  clienteNome: string | null;
  consumo: number | null;
  percentualSugerido: number;
  qualificado: boolean;
  motivo: string;
};

export type RateioQualificacao = {
  plantId: number;
  totalClientes: number;
  qualificados: number;
  ucs: RateioQualificacaoUc[];
};

export async function getQualificacao(plantId: number): Promise<RateioQualificacao> {
  const response = await apiRequest<ApiResponse<RateioQualificacao>>(`/rateio/qualificacao?plantId=${plantId}`);
  return response.data;
}