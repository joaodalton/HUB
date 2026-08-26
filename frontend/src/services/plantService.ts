import { apiRequest } from './apiClient';
import { config } from './config';

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

export type PlantRateioConfigPayload = {
  reservaPercentual?: number;
  producaoMediaManual?: number | null;
};

export type PlantStatusTone = 'success' | 'warning' | 'danger' | 'neutral';

export type PlantStatusSummary = {
  total: number;
  ativas: number;
  emImplantacao: number;
  manutencao: number;
};

export type ImportResult = { importados: number; falhas: Array<{ linha: number; erro: string }> };

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

export async function updatePlantRateioConfig(id: number, data: PlantRateioConfigPayload): Promise<PlantRow> {
  const response = await apiRequest<ApiResponse<PlantRow>>(`/plants/${id}`, {
    method: 'PUT',
    body: data
  });
  return response.data;
}

export function plantStatusLabel(status: string): string {
  const STATUS_LABELS: Record<string, string> = {
    Online: 'Ativa',
    Implantacao: 'Em Implantação',
    Manutencao: 'Manutenção',
    Inativa: 'Inativa'
  };
  return STATUS_LABELS[status] ?? status;
}

export function plantStatusTone(status: string): PlantStatusTone {
  const STATUS_TONES: Record<string, PlantStatusTone> = {
    Online: 'success',
    Implantacao: 'warning',
    Manutencao: 'danger',
    Inativa: 'neutral'
  };
  return STATUS_TONES[status] ?? 'neutral';
}

export function getPlantStatusSummary(plants: PlantRow[]): PlantStatusSummary {
  return {
    total: plants.length,
    ativas: plants.filter((plant) => plant.status === 'Online').length,
    emImplantacao: plants.filter((plant) => plant.status === 'Implantacao').length,
    manutencao: plants.filter((plant) => plant.status === 'Manutencao').length
  };
}

export async function exportPlantsCsv(): Promise<Blob> {
  const csrf = document.cookie.match(/(?:^|; )hub_csrf=([^;]*)/)?.[1];
  const resp = await fetch(`${config.apiBaseUrl}/api/v1/bulk/plants/export`, {
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

export async function importPlantsFromCsv(csvText: string): Promise<ImportResult> {
  const csrf = document.cookie.match(/(?:^|; )hub_csrf=([^;]*)/)?.[1];
  const resp = await fetch(`${config.apiBaseUrl}/api/v1/bulk/plants/import`, {
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
