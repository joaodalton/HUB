import { apiRequest } from './apiClient';
import type { PlantConnection } from './clientsService';

export type UcRow = {
  id: number;
  clienteId: number;
  clienteNome: string | null;
  codigo: string;
  codigoAneel: string | null;
  apelido: string;
  documento: string | null;
  endereco: string | null;
  cep: string | null;
  concessionaria: string | null;
  geracaoPropria: boolean;
  diaEmissaoFatura: number | null;
  consumo: string;
  baseTarifaria: string;
  desconto: string;
  tipoLigacao: 'Monofasico' | 'Bifasico' | 'Trifasico';
  inicioContrato: string | null;
  terminoContrato: string | null;
  carenciaMeses: number | null;
  percentualDescontoCarencia: string | null;
  conexoes: PlantConnection[];
};

// So os campos que a tela expoe hoje. Os demais (codigoAneel, documento,
// endereco, etc.) ficam preservados no backend mesmo sem serem enviados aqui
// -- apply_uc_fields() no backend usa data.get(campo, valor_atual), entao
// omitir um campo nunca apaga o que ja estava salvo.
export type UcPayload = {
  clienteId: number;
  codigo: string;
  apelido: string;
  consumo: string;
  baseTarifaria: string;
  desconto: string;
  tipoLigacao: string;
  conexoes: PlantConnection[];
};

type ApiResponse<T> = {
  success: boolean;
  message: string;
  data: T;
};

export async function getUcs(): Promise<UcRow[]> {
  const response = await apiRequest<ApiResponse<UcRow[]>>('/ucs');
  return response.data;
}

export async function createUc(data: UcPayload): Promise<UcRow> {
  const response = await apiRequest<ApiResponse<UcRow>>('/ucs', {
    method: 'POST',
    body: data
  });
  return response.data;
}

export async function updateUc(id: number, data: UcPayload): Promise<UcRow> {
  const response = await apiRequest<ApiResponse<UcRow>>(`/ucs/${id}`, {
    method: 'PUT',
    body: data
  });
  return response.data;
}

export async function deleteUc(id: number): Promise<void> {
  await apiRequest<ApiResponse<null>>(`/ucs/${id}`, { method: 'DELETE' });
}

export function getUcMetrics(ucs: UcRow[]) {
  const semUsina = ucs.filter((uc) => uc.conexoes.length === 0).length;

  return [
    { label: 'Total de UCs', value: String(ucs.length) },
    {
      label: 'Sem usina conectada',
      value: String(semUsina),
      tone: semUsina > 0 ? ('warning' as const) : ('success' as const)
    },
    { label: 'Geracao propria', value: String(ucs.filter((uc) => uc.geracaoPropria).length) }
  ];
}