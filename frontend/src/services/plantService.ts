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
};

export type PlantPayload = {
  nome: string;
  uc: string;
  kwPico: string;
  status: string;
  percentualDisponivel: number;
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

export function getPlantMetrics(plants: PlantRow[]) {
  return [
    { label: 'Total de usinas', value: String(plants.length) },
    { label: 'Usinas online', value: String(plants.filter((item) => item.status === 'Online').length), tone: 'success' as const },
    { label: 'Media geracao', value: getAveragePeakPower(plants) },
    { label: 'Uso total', value: `${getUsedPlantPercent(plants)}%` }
  ];
}

function getAveragePeakPower(plants: PlantRow[]): string {
  if (plants.length === 0) return '0 kWp';
  const total = plants.reduce((sum, plant) => sum + Number(String(plant.kwPico).replace(',', '.')), 0);
  return `${Math.round(total / plants.length)} kWp`;
}

function getUsedPlantPercent(plants: PlantRow[]): number {
  if (plants.length === 0) return 0;
  const available = plants.reduce((sum, plant) => sum + plant.percentualDisponivel, 0) / plants.length;
  return Math.max(0, Math.round(100 - available));
}