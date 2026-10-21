import { apiRequest, type ApiResponse } from './apiClient';

export type PlatformWorker = {
  id: number;
  nome: string;
  email: string;
  role: string;
  status: string;
  isPlatformAdmin: boolean;
  isPlatformWorker: boolean;
};

export async function getPlatformWorkers(): Promise<PlatformWorker[]> {
  const response = await apiRequest<ApiResponse<PlatformWorker[]>>('/platform/funcionarios');
  return response.data;
}

export async function createPlatformWorker(data: { nome: string; email: string; senha: string }): Promise<PlatformWorker> {
  const response = await apiRequest<ApiResponse<PlatformWorker>>('/platform/funcionarios', {
    method: 'POST',
    body: data
  });
  return response.data;
}

export async function updatePlatformWorker(id: number, data: { nome?: string; email?: string; senha?: string }): Promise<PlatformWorker> {
  const response = await apiRequest<ApiResponse<PlatformWorker>>(`/platform/funcionarios/${id}`, {
    method: 'PUT',
    body: data
  });
  return response.data;
}

export async function revokePlatformWorker(id: number): Promise<void> {
  await apiRequest<ApiResponse<PlatformWorker>>(`/platform/funcionarios/${id}`, { method: 'DELETE' });
}
