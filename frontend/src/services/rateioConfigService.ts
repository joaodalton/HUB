// frontend/src/services/rateioConfigService.ts
// Configuração global do buffer de consumo do motor de rateio -- usa o
// mesmo endpoint genérico /settings (chave/valor) que Aparência já usa,
// sem precisar de rota nova no backend.
import { apiRequest } from './apiClient';

export type RateioConfig = {
  bufferHabilitado: boolean;
  bufferPercentual: number;
};

export const DEFAULT_RATEIO_CONFIG: RateioConfig = {
  bufferHabilitado: false,
  bufferPercentual: 15
};

type ApiResponse<T> = {
  success: boolean;
  message: string;
  data: T;
};

export async function getRateioConfig(): Promise<RateioConfig> {
  const response = await apiRequest<ApiResponse<Record<string, string>>>('/settings');
  return mergeWithDefaults(response.data);
}

export async function saveRateioConfig(config: RateioConfig): Promise<RateioConfig> {
  await apiRequest<ApiResponse<Record<string, string>>>('/settings', {
    method: 'PUT',
    body: {
      rateioBufferHabilitado: String(config.bufferHabilitado),
      rateioBufferPercentual: String(config.bufferPercentual)
    }
  });
  return config;
}

function mergeWithDefaults(stored: Record<string, string>): RateioConfig {
  return {
    bufferHabilitado: stored.rateioBufferHabilitado === 'true',
    bufferPercentual: stored.rateioBufferPercentual
      ? Number(stored.rateioBufferPercentual)
      : DEFAULT_RATEIO_CONFIG.bufferPercentual
  };
}