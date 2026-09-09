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

export async function createEmpresa(data: { empresa: { nome: string; razao_social?: string; cnpj?: string; email?: string; telefone?: string }; owner: { nome: string; email: string; senha: string } }): Promise<{ empresa: EmpresaRow; owner: unknown }> {
  const response = await apiRequest<ApiResponse<{ empresa: EmpresaRow; owner: unknown }>>('/empresas', { method: 'POST', body: data });
  return response.data;
}

export async function updateEmpresaPlatform(id: number, data: Partial<EmpresaAtualUpdate> & { status?: string }): Promise<EmpresaRow> {
  const response = await apiRequest<ApiResponse<EmpresaRow>>(`/empresas/${id}`, { method: 'PUT', body: data });
  return response.data;
}

/** Campos editáveis da empresa atualmente autenticada; slug e status não fazem parte deste contrato. */
export type EmpresaAtual = {
  nome: string;
  razaoSocial: string | null;
  cnpj: string | null;
  email: string | null;
  telefone: string | null;
};

export type EmpresaAtualUpdate = Omit<EmpresaAtual, 'razaoSocial' | 'cnpj' | 'email' | 'telefone'> & {
  razaoSocial: string;
  cnpj: string;
  email: string;
  telefone: string;
};

export async function getEmpresaAtual(): Promise<EmpresaAtual> {
  const response = await apiRequest<ApiResponse<EmpresaAtual>>('/empresas/atual');
  return response.data;
}

export async function updateEmpresaAtual(data: EmpresaAtualUpdate): Promise<EmpresaAtual> {
  const response = await apiRequest<ApiResponse<EmpresaAtual>>('/empresas/atual', {
    method: 'PUT',
    body: data
  });
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
