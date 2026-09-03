import { apiRequest } from './apiClient';
import type { EmpresaRow } from './empresaService';
type ApiResponse<T> = { data: T };
export async function enterEmpresa(id: number): Promise<EmpresaRow> {
  return (await apiRequest<ApiResponse<EmpresaRow>>(`/platform/empresas/${id}/entrar`, { method: 'POST' })).data;
}
