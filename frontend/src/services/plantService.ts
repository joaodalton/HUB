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
  cidade: string;
  uf: string;
  endereco: string;
  dataAtivacao: string;
  responsavel: string;
  concessionaria: string | null;
  numModulos: number | null;
  producaoMedia: number | null;
  producaoMediaManual: number | null;
  reservaPercentual: number;
  diaEmissaoUsina: number | null;
};

export type PlantPayload = {
  nome: string;
  uc: string;
  kwPico: string;
  status: string;
  percentualDisponivel: number;
  marcaInversor?: string | null;
  telefoneProprietario?: string | null;
  emailProprietario?: string | null;
  // Opcionais -- backend aceita ausencia (mantem valor atual no update,
  // grava null na criacao). PlantCard.ts sempre manda string (mesmo vazia),
  // mas o tipo fica opcional aqui pra nao quebrar quem ainda nao envia.
  cidade?: string | null;
  uf?: string | null;
  endereco?: string | null;
  dataAtivacao?: string | null;
  responsavel?: string | null;
  concessionaria?: string | null;
  numModulos?: number | null;
  producaoMediaManual?: number | null;
  diaEmissaoUsina?: number | null;
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

export async function removePlantConnection(plantId: number, connectionId: number): Promise<void> {
  await apiRequest<ApiResponse<null>>(`/plants/${plantId}/connections/${connectionId}`, { method: 'DELETE' });
}

// Update parcial -- só os campos do motor de rateio (reserva e produção média
// manual). O backend já aceita update parcial (mantém o resto como está),
// mas PlantPayload normal exige nome/uc/kwPico/status preenchidos -- esse
// tipo aqui é só pra tela de Rateio, que edita só esses 2 campos.
export type PlantRateioConfigPayload = {
  reservaPercentual?: number;
  producaoMediaManual?: number | null;
};

export async function updatePlantRateioConfig(id: number, data: PlantRateioConfigPayload): Promise<PlantRow> {
  const response = await apiRequest<ApiResponse<PlantRow>>(`/plants/${id}`, {
    method: 'PUT',
    body: data
  });
  return response.data;
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