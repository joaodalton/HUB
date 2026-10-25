// frontend/src/services/ucService.ts
import { apiRequest, fetchAllPages, type ApiResponse, type Pagination } from './apiClient';
import type { PlantConnection } from './clientsService';

export type UcRow = {
  id: number;
  clienteId: number;
  clienteNome: string | null;
  codigo: string;
  apelido: string;
  documento: string | null;
  senhaConcessionariaConfigurada?: boolean;
  endereco: string | null;
  cep: string | null;
  concessionaria: string | null;
  geracaoPropria: boolean;
  diaEmissaoFatura: number | null;
  consumo: number | null;
  baseTarifaria: string;
  desconto: string;
  tipoLigacao: 'Monofasico' | 'Bifasico' | 'Trifasico';
  inicioContrato: string | null;
  terminoContrato: string | null;
  carenciaMeses: number | null;
  percentualDescontoCarencia: string | null;
  conexoes: PlantConnection[];
};

export type UcPayload = {
  clienteId: number;
  codigo: string;
  apelido: string;
  documento: string | null;
  endereco: string | null;
  cep: string | null;
  concessionaria: string | null;
  geracaoPropria: boolean;
  diaEmissaoFatura: number | null;
  consumo: number | null;
  baseTarifaria: string;
  desconto: string;
  tipoLigacao: string;
  inicioContrato: string | null;
  terminoContrato: string | null;
  carenciaMeses: number | null;
  percentualDescontoCarencia: string | null;
  senhaConcessionaria?: string;
  conexoes: Array<{ plantId: number; percentual: string }>;
};


export type UcsPage = { data: UcRow[]; pagination: Pagination };

export async function getUcsPage(page = 1, pageSize = 50): Promise<UcsPage> {
  const response = await apiRequest<ApiResponse<UcRow[]> & Pick<UcsPage, 'pagination'>>(
    `/ucs?page=${page}&pageSize=${pageSize}`
  );
  return { data: response.data, pagination: response.pagination };
}

// Lista completa (todas as paginas) -- mantido pra quem precisa do cadastro
// inteiro pra selecao/calculo, sem expor paginacao a esses consumidores.
export async function getUcs(): Promise<UcRow[]> {
  return fetchAllPages((page, pageSize) => getUcsPage(page, pageSize));
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
  return [
    { label: 'Total de UCs', value: String(ucs.length) },
    {
      label: 'Conectadas a usina',
      value: String(ucs.filter((uc) => uc.conexoes.length > 0).length),
      tone: 'success' as const
    },
    {
      label: 'Sem usina',
      value: String(ucs.filter((uc) => uc.conexoes.length === 0).length),
      tone: 'warning' as const
    },
    { label: 'Geracao propria', value: String(ucs.filter((uc) => uc.geracaoPropria).length) }
  ];
}

export async function getConcessionariaPassword(ucId: number): Promise<string> {
  const response = await apiRequest<ApiResponse<{ senhaConcessionaria: string }>>(`/ucs/${ucId}/senha-concessionaria`);
  return response.data.senhaConcessionaria;
}
