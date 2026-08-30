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

export type EmpresaDocumentos = {
  cnpj: { id: number; nome: string } | null;
  estatuto: { id: number; nome: string } | null;
};

export async function getEmpresaDocumentos(): Promise<EmpresaDocumentos> {
  const response = await apiRequest<ApiResponse<EmpresaDocumentos>>('/empresas/documentos');
  return response.data;
}
