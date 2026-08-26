import { apiRequest } from './apiClient';
import { config } from './config';

export type PlantConnection = {
  id: number;
  plantId: number;
  usina: string;
  percentual: string;
  percentualManual?: boolean;
};

export type ClientUc = {
  id: number | string;
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

export type ClientRow = {
  id: number;
  nome: string;
  cpf: string;
  email: string;
  telefone: string | null;
  dataNascimento: string | null;
  uc: string;
  usina: string;
  consumo: string;
  status: string;
  concessionaria: string;
  ucs: ClientUc[];
};

export type ClientPayload = {
  nome: string;
  cpf: string;
  email: string;
  telefone: string;
  dataNascimento: string | null;
  concessionaria: string;
  ucs: ClientUc[];
};

export const concessionarias = ['Copel'];

export type ImportResult = { importados: number; falhas: Array<{ linha: number; erro: string }> };

type ApiResponse<T> = {
  success: boolean;
  message: string;
  data: T;
};

export async function getClients(): Promise<ClientRow[]> {
  const response = await apiRequest<ApiResponse<ClientRow[]>>('/clients');
  return response.data;
}

export async function createClient(data: ClientPayload): Promise<ClientRow> {
  const response = await apiRequest<ApiResponse<ClientRow>>('/clients', {
    method: 'POST',
    body: data
  });
  return response.data;
}

export async function updateClient(id: number, data: ClientPayload): Promise<ClientRow> {
  const response = await apiRequest<ApiResponse<ClientRow>>(`/clients/${id}`, {
    method: 'PUT',
    body: data
  });
  return response.data;
}

export async function deleteClient(id: number): Promise<void> {
  await apiRequest<ApiResponse<null>>(`/clients/${id}`, { method: 'DELETE' });
}

export function getClientMetrics(clients: ClientRow[]) {
  return [
    { label: 'Total de clientes', value: String(clients.length) },
    {
      label: 'Esperando usina',
      value: String(clients.filter((item) => item.status === 'Esperando usina').length),
      tone: 'warning' as const
    },
    {
      label: 'Esperando rateio',
      value: String(clients.filter((item) => item.status === 'Esperando rateio').length),
      tone: 'warning' as const
    },
    {
      label: 'Concluidos',
      value: String(clients.filter((item) => item.status === 'Concluido').length),
      tone: 'success' as const
    }
  ];
}

export async function exportClientsCsv(): Promise<Blob> {
  const csrf = document.cookie.match(/(?:^|; )hub_csrf=([^;]*)/)?.[1];
  const resp = await fetch(`${config.apiBaseUrl}/api/v1/bulk/clients/export`, {
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

export async function importClientsFromCsv(csvText: string): Promise<ImportResult> {
  const csrf = document.cookie.match(/(?:^|; )hub_csrf=([^;]*)/)?.[1];
  const resp = await fetch(`${config.apiBaseUrl}/api/v1/bulk/clients/import`, {
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
