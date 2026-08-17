import { apiRequest } from './apiClient';

export type UserRole = 'owner' | 'admin' | 'operator' | 'financial' | 'viewer';

export type UserRow = {
  id: number;
  empresaId: number;
  nome: string;
  email: string;
  role: UserRole;
  status: 'ativo' | 'inativo';
  emailVerified: boolean;
  mustChangePassword: boolean;
};

export type UserPayload = {
  nome: string;
  email: string;
  senha: string;
  role: Exclude<UserRole, 'owner'>;
};

type ApiResponse<T> = {
  success: boolean;
  message: string;
  data: T;
};

export async function getUsers(): Promise<UserRow[]> {
  const response = await apiRequest<ApiResponse<UserRow[]>>('/users');
  return response.data;
}

export async function createUser(data: UserPayload): Promise<UserRow> {
  const response = await apiRequest<ApiResponse<UserRow>>('/users', {
    method: 'POST',
    body: data
  });
  return response.data;
}

export async function setUserActive(id: number, ativo: boolean): Promise<UserRow> {
  const response = await apiRequest<ApiResponse<UserRow>>(`/users/${id}/ativo`, {
    method: 'PUT',
    body: { ativo }
  });
  return response.data;
}