import { apiRequest, fetchAllPages, type ApiResponse, type Pagination } from './apiClient';

export type PlantConnection = {
  id: number;
  plantId: number;
  usina: string;
  percentual: string;
};

export type ClientUc = {
  id: number | string;
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
  senhaConcessionaria?: string;
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


export type ClientsPage = { data: ClientRow[]; pagination: Pagination };

export async function getClientsPage(page = 1, pageSize = 50): Promise<ClientsPage> {
  const response = await apiRequest<ApiResponse<ClientRow[]> & Pick<ClientsPage, 'pagination'>>(
    `/clients?page=${page}&pageSize=${pageSize}`
  );
  return { data: response.data, pagination: response.pagination };
}

// Lista completa (todas as paginas) -- mantido pra quem precisa do cadastro
// inteiro pra selecao/calculo (RateioWizard, FaturasPage, relatorios etc.),
// sem expor paginacao a esses consumidores.
export async function getClients(): Promise<ClientRow[]> {
  return fetchAllPages((page, pageSize) => getClientsPage(page, pageSize));
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
