// frontend/src/services/plantService.ts
import { apiRequest } from './apiClient';

export type PlantRow = {
  id: number;
  nome: string;
  uc: string;
  kwPico: string;
  mediaGeracao: string;
  status: string;
  percentualDisponivel: number;
  marcaInversor: string | null;
  telefoneProprietario: string | null;
  emailProprietario: string | null;
  // Campos do mockup da reforma da tela de Usinas que ainda nao tem
  // contrapartida no backend (Plant model / plant_service.py). Ficam
  // opcionais e undefined ate serem adicionados la -- a UI mostra "-"
  // quando ausentes. Nao inventar valor nenhum aqui.
  cidade?: string;
  uf?: string;
  endereco?: string;
  dataAtivacao?: string;
  responsavel?: string;
};

export type PlantPayload = {
  nome: string;
  uc: string;
  kwPico: string;
  status: string;
  percentualDisponivel: number;
  // Opcionais: PlantCard.ts ainda nao expoe esses campos no formulario
  // (adiamento registrado no PROGRESS.md, junto da reforma geral do frontend).
  // Backend ja aceita ausencia dessas chaves (mantem o valor atual no update,
  // grava null na criacao), entao nao precisam ser obrigatorias aqui.
  marcaInversor?: string | null;
  telefoneProprietario?: string | null;
  emailProprietario?: string | null;
};

type ApiResponse<T> = {
  success: boolean;
  message: string;
  data: T;
};

export async function getPlants(): Promise<PlantRow[]> {
  const response = await apiRequest<ApiResponse<PlantRow[]>>('/plants');
  return response.data;
}

export async function getAvailablePlants(): Promise<PlantRow[]> {
  const plants = await getPlants();
  return plants.filter((plant) => plant.percentualDisponivel > 0);
}

export async function createPlant(data: PlantPayload): Promise<PlantRow> {
  const response = await apiRequest<ApiResponse<PlantRow>>('/plants', {
    method: 'POST',
    body: data
  });
  return response.data;
}

export async function updatePlant(id: number, data: PlantPayload): Promise<PlantRow> {
  const response = await apiRequest<ApiResponse<PlantRow>>(`/plants/${id}`, {
    method: 'PUT',
    body: data
  });
  return response.data;
}

export async function deletePlant(id: number): Promise<void> {
  await apiRequest<ApiResponse<null>>(`/plants/${id}`, { method: 'DELETE' });
}

// Status "cru" vem do backend (Online/Implantacao/Manutencao/Inativa, ver
// PlantCard.ts). Esses dois helpers so cuidam da apresentacao (rotulo PT-BR +
// cor) -- nao mudam o valor gravado, pra nao quebrar o formulario de edicao
// nem dado ja salvo.
export type PlantStatusTone = 'success' | 'warning' | 'danger' | 'neutral';

const STATUS_LABELS: Record<string, string> = {
  Online: 'Ativa',
  Implantacao: 'Em Implantação',
  Manutencao: 'Manutenção',
  Inativa: 'Inativa'
};

const STATUS_TONES: Record<string, PlantStatusTone> = {
  Online: 'success',
  Implantacao: 'warning',
  Manutencao: 'danger',
  Inativa: 'neutral'
};

export function plantStatusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status;
}

export function plantStatusTone(status: string): PlantStatusTone {
  return STATUS_TONES[status] ?? 'neutral';
}

export type PlantStatusSummary = {
  total: number;
  ativas: number;
  emImplantacao: number;
  manutencao: number;
};

export function getPlantStatusSummary(plants: PlantRow[]): PlantStatusSummary {
  return {
    total: plants.length,
    ativas: plants.filter((plant) => plant.status === 'Online').length,
    emImplantacao: plants.filter((plant) => plant.status === 'Implantacao').length,
    manutencao: plants.filter((plant) => plant.status === 'Manutencao').length
  };
}