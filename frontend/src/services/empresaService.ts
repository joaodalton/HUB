import { apiRequest } from './apiClient';

export type EmpresaRow = {
  id: number;
  nome: string;
  slug: string;
  status: string;
  cnpj: string | null;
  email: string | null;
  telefone: string | null;
  totalUsuarios: number;
  totalClientes: number;
  ownerEmail: string | null;
};

export type EmpresaDetalhe = EmpresaRow & {
  razaoSocial: string | null;
  totalClientes: number;
  totalUcs: number;
  totalUsinas: number;
  totalPendencias: number;
  totalFaturas: number;
  totalRateios: number;
  totalDocumentos: number;
  totalConvites: number;
};

export type EmpresaCreatePayload = {
  empresa: {
    nome: string;
    razaoSocial?: string;
    cnpj?: string;
    email?: string;
    telefone?: string;
  };
  owner: {
    nome: string;
    email: string;
    senha: string;
  };
};

type ApiResponse<T> = { success: boolean; message: string; data: T };

export type EmpresaUpdatePayload = {
  nome?: string;
  razaoSocial?: string;
  cnpj?: string;
  email?: string;
  telefone?: string;
  status?: string;
};

export async function getEmpresas(): Promise<EmpresaRow[]> {
  const response = await apiRequest<ApiResponse<EmpresaRow[]>>('/empresas');
  return response.data;
}

export async function getEmpresaDetalhe(empresaId: number): Promise<EmpresaDetalhe> {
  const response = await apiRequest<ApiResponse<EmpresaDetalhe>>(`/empresas/${empresaId}`);
  return response.data;
}

export async function createEmpresa(data: EmpresaCreatePayload): Promise<EmpresaDetalhe> {
  const response = await apiRequest<ApiResponse<EmpresaDetalhe>>('/empresas', {
    method: 'POST',
    body: data
  });
  return response.data;
}

export async function updateEmpresa(empresaId: number, data: EmpresaUpdatePayload): Promise<EmpresaDetalhe> {
  const response = await apiRequest<ApiResponse<EmpresaDetalhe>>(`/empresas/${empresaId}`, {
    method: 'PUT',
    body: data
  });
  return response.data;
}

export async function entraEmpresa(empresaId: number): Promise<{ empresaId: number; empresaNome: string }> {
  const response = await apiRequest<ApiResponse<{ empresaId: number; empresaNome: string }>>(
    `/empresas/${empresaId}/entrar`,
    { method: 'POST' }
  );
  return response.data;
}

export async function sairPlataforma(): Promise<void> {
  await apiRequest<ApiResponse<null>>('/empresas/sair-plataforma', { method: 'POST' });
}

export async function deleteEmpresa(empresaId: number, confirmacao: string): Promise<void> {
  await apiRequest<ApiResponse<null>>(`/empresas/${empresaId}`, {
    method: 'DELETE',
    body: { confirmacao }
  });
}
