import { apiRequest } from './apiClient';
import type { EmpresaRow } from './empresaService';

type ApiResponse<T> = {
  success: boolean;
  message: string;
  data: T;
};

export type PlatformOverview = {
  totalEmpresas: number;
  totalUsuarios: number;
};

export type PlatformEmpresa = EmpresaRow & {
  createdAt?: string | null;
};

export async function getPlatformOverview(): Promise<PlatformOverview> {
  const response = await apiRequest<ApiResponse<PlatformOverview>>('/platform');
  return response.data;
}

export async function getPlatformEmpresas(): Promise<PlatformEmpresa[]> {
  const response = await apiRequest<ApiResponse<PlatformEmpresa[]>>('/platform/empresas');
  return response.data;
}

export async function entrarNaEmpresa(id: number): Promise<EmpresaRow> {
  const response = await apiRequest<ApiResponse<EmpresaRow>>(`/platform/empresas/${id}/entrar`, {
    method: 'POST'
  });
  return response.data;
}

export async function sairDaVisualizacao(): Promise<void> {
  await apiRequest<ApiResponse<null>>('/platform/sair', { method: 'POST' });
}

export const enterEmpresa = entrarNaEmpresa;
