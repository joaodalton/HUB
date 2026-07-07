export type ClientRow = {
  id: string;
  nome: string;
  cpf: string;
  email: string;
  uc: string;
  usina: string;
  consumo: string;
  status: string;
  documentos: string[];
  ucs: string[];
};

export type PlantRow = {
  nome: string;
  uc: string;
  mediaGeracao: string;
  status: string;
};

const clients: ClientRow[] = [
  {
    id: 'cliente-1',
    nome: 'Ana Ribeiro',
    cpf: '123.456.789-10',
    email: 'ana@email.com',
    uc: 'UC-1042',
    usina: 'Solar Norte',
    consumo: '480 kWh',
    status: 'Concluido',
    documentos: ['contrato-ana.pdf'],
    ucs: ['UC-1042']
  },
  {
    id: 'cliente-2',
    nome: 'Carlos Mendes',
    cpf: '222.333.444-55',
    email: 'carlos@email.com',
    uc: 'UC-1189',
    usina: 'A definir',
    consumo: '620 kWh',
    status: 'Esperando usina',
    documentos: [],
    ucs: ['UC-1189']
  },
  {
    id: 'cliente-3',
    nome: 'JM Comercio',
    cpf: '12.345.678/0001-90',
    email: 'financeiro@jm.com',
    uc: 'UC-1320',
    usina: 'Solar Leste',
    consumo: '1.840 kWh',
    status: 'Esperando rateio',
    documentos: ['termo-jm.pdf', 'documentos-jm.zip'],
    ucs: ['UC-1320', 'UC-1321']
  },
  {
    id: 'cliente-4',
    nome: 'Patricia Alves',
    cpf: '987.654.321-00',
    email: 'patricia@email.com',
    uc: 'UC-1404',
    usina: 'Solar Norte',
    consumo: '390 kWh',
    status: 'Concluido',
    documentos: [],
    ucs: ['UC-1404']
  }
];

const plants: PlantRow[] = [
  { nome: 'Solar Norte', uc: 'UC-G001', mediaGeracao: '2.400 kWh', status: 'Online' },
  { nome: 'Solar Leste', uc: 'UC-G002', mediaGeracao: '1.820 kWh', status: 'Online' },
  { nome: 'Solar Serra', uc: 'UC-G003', mediaGeracao: '0 kWh', status: 'Implantacao' }
];

export function getClients(): ClientRow[] {
  return clients;
}

export function getPlants(): PlantRow[] {
  return plants;
}

export function getAvailablePlantNames(): string[] {
  return plants.map((plant) => plant.nome);
}

export function createClient(data: Omit<ClientRow, 'id' | 'status'>): ClientRow {
  const client: ClientRow = {
    ...data,
    id: crypto.randomUUID(),
    status: getClientStatus(data.usina)
  };

  clients.unshift(client);
  return client;
}

export function updateClient(id: string, data: Omit<ClientRow, 'id' | 'status'>): ClientRow | null {
  const index = clients.findIndex((client) => client.id === id);

  if (index < 0) return null;

  clients[index] = {
    ...data,
    id,
    status: getClientStatus(data.usina)
  };

  return clients[index];
}

export function deleteClient(id: string): void {
  const index = clients.findIndex((client) => client.id === id);
  if (index >= 0) clients.splice(index, 1);
}

export function getClientMetrics() {
  return [
    { label: 'Total de clientes', value: String(clients.length) },
    { label: 'Esperando usina', value: String(clients.filter((item) => item.status === 'Esperando usina').length), tone: 'warning' as const },
    { label: 'Esperando rateio', value: String(clients.filter((item) => item.status === 'Esperando rateio').length), tone: 'warning' as const },
    { label: 'Concluidos', value: String(clients.filter((item) => item.status === 'Concluido').length), tone: 'success' as const }
  ];
}

export function getPlantMetrics() {
  return [
    { label: 'Total de usinas', value: String(plants.length) },
    { label: 'Usinas online', value: String(plants.filter((item) => item.status === 'Online').length), tone: 'success' as const },
    { label: 'Media geracao', value: '1.407 kWh' },
    { label: 'Uso total', value: '68%' }
  ];
}

function getClientStatus(usina: string): string {
  return usina && usina !== 'A definir' ? 'Concluido' : 'Esperando usina';
}
