import { apiRequest } from './apiClient';
import type { EmpresaRow } from './empresaService';

type ApiResponse<T> = {
  success: boolean;
  message: string;
  data: T;
};

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
