import { apiRequest } from './apiClient';

export type PlantConnection = {
  plantId: number;
  usina: string;
  percentual: string;
};

export type ClientUc = {
  id: number | string;
  codigo: string;
  apelido: string;
  consumo: string;
  baseTarifaria: string;
  desconto: string;
  tipoLigacao: 'Monofasico' | 'Bifasico' | 'Trifasico';
  conexoes: PlantConnection[];
};

export type ClientDocument = {
  id: string;
  nome: string;
  dataUrl?: string;
};

export type ClientRow = {
  id: number;
  nome: string;
  cpf: string;
  email: string;
  uc: string;
  usina: string;
  consumo: string;
  status: string;
  concessionaria: string;
  documentos: ClientDocument[];
  ucs: ClientUc[];
};

export type ClientPayload = {
  nome: string;
  cpf: string;
  email: string;
  concessionaria: string;
  ucs: ClientUc[];
};

export const concessionarias = ['Copel'];

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