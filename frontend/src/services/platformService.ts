import { apiRequest, type ApiResponse } from './apiClient';
import type { EmpresaRow } from './empresaService';


export type PlatformOverview = {
  totalEmpresas: number;
  totalUsuarios: number;
};

export type PlatformEmpresa = Omit<EmpresaRow, 'totalUsuarios'> & {
  totalClientes: number;
  totalUcs: number;
  totalUsinas: number;
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

export async function deletarEmpresa(empresaId: number): Promise<void> {
  await apiRequest<ApiResponse<null>>(`/platform/empresas/${empresaId}`, { method: 'DELETE' });
}

export type NeonBranchStorage = { nome: string; tamanhoBytes: number };
export type NeonEnvironmentStorage = {
  ambiente: string;
  projectId: string;
  totalBytes: number;
  branches: NeonBranchStorage[];
  limiteBytes: number | null;
  pgVersion: number | null;
  computeStatus: string | null;
};
export type NeonStorageSummary = {
  ambienteAtual: string;
  ambientes: NeonEnvironmentStorage[];
};

export async function getNeonStorage(): Promise<NeonStorageSummary> {
  const response = await apiRequest<ApiResponse<NeonStorageSummary>>('/platform/neon-storage');
  return response.data;
}

export const enterEmpresa = entrarNaEmpresa;
