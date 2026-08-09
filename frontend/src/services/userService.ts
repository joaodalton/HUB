import { apiRequest } from './apiClient';

export type UserRow = {
  id: number;
  email: string;
  papel: 'admin' | 'viewer';
  ativo: boolean;
};

export type UserPayload = {
  email: string;
  senha: string;
  papel: 'admin' | 'viewer';
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