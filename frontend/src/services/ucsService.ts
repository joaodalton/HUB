import { apiRequest } from './apiClient';
import { config } from './config';
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
  codigoAneel: string | null;
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
  conexoes: PlantConnection[];
};

export type ImportResult = { importados: number; falhas: Array<{ linha: number; erro: string }> };

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

export async function exportUcsCsv(): Promise<Blob> {
  const csrf = document.cookie.match(/(?:^|; )hub_csrf=([^;]*)/)?.[1];
  const resp = await fetch(`${config.apiBaseUrl}/api/v1/bulk/ucs/export`, {
    method: 'GET',
    credentials: 'include',
    headers: csrf ? { 'X-CSRF-Token': csrf } : {},
  });
  if (resp.status === 401) {
    window.location.href = '/login';
    throw new Error('Não autenticado.');
  }
  if (!resp.ok) {
    const data = await resp.json().catch(() => null);
    throw new Error(data?.message || data?.error || 'Falha na exportação.');
  }
  return resp.blob();
}

export async function importUcsFromCsv(csvText: string): Promise<ImportResult> {
  const csrf = document.cookie.match(/(?:^|; )hub_csrf=([^;]*)/)?.[1];
  const resp = await fetch(`${config.apiBaseUrl}/api/v1/bulk/ucs/import`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'text/csv; charset=utf-8',
      'X-CSRF-Token': csrf ? decodeURIComponent(csrf) : '',
    },
    body: csvText,
  });
  if (resp.status === 401) {
    window.location.href = '/login';
    throw new Error('Não autenticado.');
  }
  if (!resp.ok) {
    const data = await resp.json().catch(() => null);
    throw new Error(data?.message || data?.error || 'Falha na importação.');
  }
  const json = await resp.json();
  return json.data;
}
