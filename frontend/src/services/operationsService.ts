export type PlantConnection = {
  usina: string;
  percentual: string;
};

export type ClientUc = {
  id: string;
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
  id: string;
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

export type PlantRow = {
  id: string;
  nome: string;
  uc: string;
  kwPico: string;
  mediaGeracao: string;
  status: string;
  percentualDisponivel: number;
};

const STORAGE_KEY = 'hub.operations.v1';
export const concessionarias = ['Copel'];

const initialClients: ClientRow[] = [
  {
    id: 'cliente-1',
    nome: 'Ana Ribeiro',
    cpf: '123.456.789-10',
    email: 'ana@email.com',
    uc: 'UC-1042',
    usina: 'Solar Norte',
    consumo: '480 kWh',
    status: 'Concluido',
    concessionaria: 'Copel',
    documentos: [{ id: 'doc-1', nome: 'contrato-ana.pdf' }],
    ucs: [{
      id: 'uc-1',
      codigo: 'UC-1042',
      apelido: 'Casa',
      consumo: '480 kWh',
      baseTarifaria: 'B1 Residencial',
      desconto: '15%',
      tipoLigacao: 'Bifasico',
      conexoes: [{ usina: 'Solar Norte', percentual: '100' }]
    }]
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
    concessionaria: 'Copel',
    documentos: [],
    ucs: [{
      id: 'uc-2',
      codigo: 'UC-1189',
      apelido: 'Apartamento',
      consumo: '620 kWh',
      baseTarifaria: 'B1 Residencial',
      desconto: '12%',
      tipoLigacao: 'Monofasico',
      conexoes: []
    }]
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
    concessionaria: 'Copel',
    documentos: [
      { id: 'doc-2', nome: 'termo-jm.pdf' },
      { id: 'doc-3', nome: 'documentos-jm.zip' }
    ],
    ucs: [{
      id: 'uc-3',
      codigo: 'UC-1320',
      apelido: 'Matriz',
      consumo: '1.100 kWh',
      baseTarifaria: 'B3 Comercial',
      desconto: '18%',
      tipoLigacao: 'Trifasico',
      conexoes: [{ usina: 'Solar Leste', percentual: '70' }]
    }, {
      id: 'uc-4',
      codigo: 'UC-1321',
      apelido: 'Deposito',
      consumo: '740 kWh',
      baseTarifaria: 'B3 Comercial',
      desconto: '18%',
      tipoLigacao: 'Trifasico',
      conexoes: [{ usina: 'Solar Leste', percentual: '30' }]
    }]
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
    concessionaria: 'Copel',
    documentos: [],
    ucs: [{
      id: 'uc-5',
      codigo: 'UC-1404',
      apelido: 'Casa',
      consumo: '390 kWh',
      baseTarifaria: 'B1 Residencial',
      desconto: '15%',
      tipoLigacao: 'Bifasico',
      conexoes: [{ usina: 'Solar Norte', percentual: '100' }]
    }]
  }
];

const initialPlants: PlantRow[] = [
  { id: 'usina-1', nome: 'Solar Norte', uc: 'UC-G001', kwPico: '520', mediaGeracao: '2.400 kWh', status: 'Online', percentualDisponivel: 34 },
  { id: 'usina-2', nome: 'Solar Leste', uc: 'UC-G002', kwPico: '410', mediaGeracao: '1.820 kWh', status: 'Online', percentualDisponivel: 18 },
  { id: 'usina-3', nome: 'Solar Serra', uc: 'UC-G003', kwPico: '300', mediaGeracao: '0 kWh', status: 'Implantacao', percentualDisponivel: 0 }
];

const storedData = loadData();
const clients: ClientRow[] = storedData.clients;
const plants: PlantRow[] = storedData.plants;

export function getClients(): ClientRow[] {
  return clients;
}

export function getPlants(): PlantRow[] {
  return plants;
}

export function getAvailablePlants(): PlantRow[] {
  return plants.filter((plant) => plant.percentualDisponivel > 0);
}

export function createClient(data: Omit<ClientRow, 'id' | 'status'>): ClientRow {
  const client = normalizeClient({
    ...data,
    id: crypto.randomUUID(),
    status: getClientStatus(data.usina, data.ucs)
  });

  clients.unshift(client);
  persistData();
  return client;
}

export function updateClient(id: string, data: Omit<ClientRow, 'id' | 'status'>): ClientRow | null {
  const index = clients.findIndex((client) => client.id === id);

  if (index < 0) return null;

  clients[index] = normalizeClient({
    ...data,
    id,
    status: getClientStatus(data.usina, data.ucs)
  });

  persistData();
  return clients[index];
}

export function deleteClient(id: string): void {
  const index = clients.findIndex((client) => client.id === id);

  if (index >= 0) {
    clients.splice(index, 1);
    persistData();
  }
}

export function createPlant(data: Omit<PlantRow, 'id' | 'mediaGeracao'>): PlantRow {
  const plant: PlantRow = {
    ...data,
    id: crypto.randomUUID(),
    mediaGeracao: `${data.kwPico} kWp`
  };

  plants.unshift(plant);
  persistData();
  return plant;
}

export function updatePlant(id: string, data: Omit<PlantRow, 'id' | 'mediaGeracao'>): PlantRow | null {
  const index = plants.findIndex((plant) => plant.id === id);

  if (index < 0) return null;

  plants[index] = {
    ...data,
    id,
    mediaGeracao: `${data.kwPico} kWp`
  };
  persistData();
  return plants[index];
}

export function deletePlant(id: string): void {
  const index = plants.findIndex((plant) => plant.id === id);

  if (index >= 0) {
    plants.splice(index, 1);
    persistData();
  }
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
    { label: 'Media geracao', value: getAveragePeakPower() },
    { label: 'Uso total', value: `${getUsedPlantPercent()}%` }
  ];
}

function getClientStatus(usina: string, ucs: ClientUc[]): string {
  if (ucs.some((uc) => uc.conexoes.length > 1)) return 'Esperando rateio';
  if (ucs.some((uc) => uc.conexoes.length > 0) || (usina && usina !== 'A definir')) return 'Concluido';
  return 'Esperando usina';
}

function normalizeClient(client: ClientRow): ClientRow {
  const rawUcs = (client.ucs ?? []) as Array<ClientUc | string>;
  const normalizedUcs = rawUcs.map(normalizeUc);
  const firstUc = normalizedUcs[0];
  const firstConnection = firstUc?.conexoes[0]?.usina;
  const rawDocuments = (client.documentos ?? []) as Array<ClientDocument | string>;

  return {
    ...client,
    uc: firstUc?.codigo ?? client.uc,
    usina: firstConnection ?? client.usina ?? 'A definir',
    consumo: firstUc?.consumo ?? client.consumo,
    concessionaria: client.concessionaria ?? concessionarias[0],
    documentos: rawDocuments.map((documento) => {
      if (typeof documento === 'string') {
        return { id: crypto.randomUUID(), nome: documento };
      }

      return documento;
    }),
    ucs: normalizedUcs,
    status: getClientStatus(client.usina, normalizedUcs)
  };
}

function normalizeUc(uc: ClientUc | string): ClientUc {
  if (typeof uc === 'string') {
    return {
      id: crypto.randomUUID(),
      codigo: uc,
      apelido: '',
      consumo: '',
      baseTarifaria: 'B1',
      desconto: '',
      tipoLigacao: 'Monofasico',
      conexoes: []
    };
  }

  return {
    ...uc,
    id: uc.id ?? crypto.randomUUID(),
    baseTarifaria: uc.baseTarifaria || 'B1',
    tipoLigacao: uc.tipoLigacao || 'Monofasico',
    conexoes: uc.conexoes ?? []
  };
}

function loadData(): { clients: ClientRow[]; plants: PlantRow[] } {
  const saved = window.localStorage.getItem(STORAGE_KEY);

  if (!saved) return { clients: initialClients, plants: initialPlants };

  try {
    const parsed = JSON.parse(saved) as { clients?: ClientRow[]; plants?: PlantRow[] };

    return {
      clients: parsed.clients?.length ? parsed.clients.map(normalizeClient) : initialClients,
      plants: parsed.plants?.length ? parsed.plants.map(normalizePlant) : initialPlants
    };
  } catch {
    return { clients: initialClients, plants: initialPlants };
  }
}

function persistData(): void {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ clients, plants }));
}

function normalizePlant(plant: PlantRow): PlantRow {
  return {
    ...plant,
    id: plant.id ?? crypto.randomUUID(),
    kwPico: plant.kwPico ?? plant.mediaGeracao.replace(/[^\d,.]/g, ''),
    percentualDisponivel: Number(plant.percentualDisponivel) || 0
  };
}

function getAveragePeakPower(): string {
  if (plants.length === 0) return '0 kWp';

  const total = plants.reduce((sum, plant) => sum + Number(plant.kwPico.replace(',', '.')), 0);
  return `${Math.round(total / plants.length)} kWp`;
}

function getUsedPlantPercent(): number {
  if (plants.length === 0) return 0;

  const available = plants.reduce((sum, plant) => sum + plant.percentualDisponivel, 0) / plants.length;
  return Math.max(0, Math.round(100 - available));
}
