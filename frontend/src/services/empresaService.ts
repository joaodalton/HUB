import { apiRequest } from './apiClient';

export type EmpresaRow = {
  id: number;
  nome: string;
  slug: string;
  status: string;
  cnpj: string | null;
  totalUsuarios: number;
};

type ApiResponse<T> = { data: T };

export async function getEmpresas(): Promise<EmpresaRow[]> {
  const response = await apiRequest<ApiResponse<EmpresaRow[]>>('/empresas');
  return response.data;
}
