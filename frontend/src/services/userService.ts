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
  isPlatformAdmin?: boolean;
};

export type UserPayload = {
  nome: string;
  email: string;
  senha?: string;
  role: Exclude<UserRole, 'owner'>;
};

type ApiResponse<T> = { success: boolean; message: string; data: T };

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

export async function updateUser(id: number, data: Partial<UserPayload>): Promise<UserRow> {
  const response = await apiRequest<ApiResponse<UserRow>>(`/users/${id}`, {
    method: 'PUT',
    body: data
  });
  return response.data;
}

export async function setUserActive(id: number, ativo: boolean): Promise<UserRow> {
  const response = await apiRequest<ApiResponse<UserRow>>(`/users/${id}`, {
    method: 'PUT',
    body: { ativo }
  });
  return response.data;
}

export async function deleteUser(id: number): Promise<void> {
  await apiRequest<ApiResponse<null>>(`/users/${id}`, { method: 'DELETE' });
}

export async function resetUserPassword(
  userId: number,
  novaSenha: string,
  confirmacao: string
): Promise<void> {
  await apiRequest<ApiResponse<null>>(`/users/${userId}/redefinir-senha`, {
    method: 'POST',
    body: { nova_senha: novaSenha, confirmacao }
  });
}
