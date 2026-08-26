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
  const response = await apiRequest<ApiResponse<RateioPreview[]>>(
    `/rateio/preview?plantId=${plantId}`
  );
  // Backend sempre devolve array (suporta calcular várias usinas de uma vez) --
  // aqui a gente sempre filtra por 1 plantId, então é sempre o primeiro item.
  return response.data[0];
}

export async function aplicarRateio(
  competencia: string,
  plantId: number
): Promise<RateioPreview[]> {
  const response = await apiRequest<ApiResponse<RateioPreview[]>>('/rateio/aplicar', {
    method: 'POST',
    body: { competencia, plantId },
  });
  return response.data;
}

export type RateioConfirmacaoResultado = {
  plantId: number;
  competencia: string;
  conexoesCriadas: number;
  conexoesAtualizadas: number;
  ucs: Array<{
    ucId: number;
    ucCodigo: string;
    clienteNome: string | null;
    percentual: number;
  }>;
};

export async function confirmarSelecaoRateio(
  plantId: number,
  competencia: string,
  selecoes: Array<{ ucId: number; percentual: number }>
): Promise<RateioConfirmacaoResultado> {
  const response = await apiRequest<ApiResponse<RateioConfirmacaoResultado>>(
    '/rateio/confirmar',
    {
      method: 'POST',
      body: { plantId, competencia, selecoes },
    }
  );
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

export async function getQualificacao(
  plantId: number
): Promise<RateioQualificacao> {
  const response = await apiRequest<ApiResponse<RateioQualificacao>>(
    `/rateio/qualificacao?plantId=${plantId}`
  );
  return response.data;
}

export type RateioDistribuicaoConexao = {
  id: number;
  plantId: number;
  usina: string;
  percentual: number;
  percentualManual: boolean;
};

export type RateioDistribuicaoResultado = {
  plantId: number;
  conexoes: RateioDistribuicaoConexao[];
};

// Edita percentual de conexoes que JA EXISTEM (botao "Editar distribuicao"
// na tela de Usina) -- diferente de confirmarSelecaoRateio, que so roda
// dentro do wizard e pode criar conexao nova. Ver rateio_service.py.
export async function atualizarDistribuicao(
  plantId: number,
  atualizacoes: Array<{ connectionId: number; percentual: number }>
): Promise<RateioDistribuicaoResultado> {
  const response = await apiRequest<ApiResponse<RateioDistribuicaoResultado>>(
    '/rateio/distribuicao',
    {
      method: 'PUT',
      body: { plantId, atualizacoes },
    }
  );
  return response.data;
}
