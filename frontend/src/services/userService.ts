import { apiRequest, fetchAllPages, type ApiResponse, type Pagination } from './apiClient';

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

export type UserUpdatePayload = Partial<Pick<UserRow, 'nome' | 'email' | 'role'>> & {
  senha?: string;
};


export type UsersPage = { data: UserRow[]; pagination: Pagination };

export async function getUsersPage(page = 1, pageSize = 50): Promise<UsersPage> {
  const response = await apiRequest<ApiResponse<UserRow[]> & Pick<UsersPage, 'pagination'>>(
    `/users?page=${page}&pageSize=${pageSize}`
  );
  return { data: response.data, pagination: response.pagination };
}

// Lista completa (todas as paginas) -- mantido pra quem precisa de todos os
// usuarios (ex.: seletor de responsavel), sem expor paginacao a esses
// consumidores.
export async function getUsers(): Promise<UserRow[]> {
  return fetchAllPages((page, pageSize) => getUsersPage(page, pageSize));
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

export async function updateUser(id: number, data: UserUpdatePayload): Promise<UserRow> {
  const response = await apiRequest<ApiResponse<UserRow>>(`/users/${id}`, { method: 'PUT', body: data });
  return response.data;
}

export async function deleteUser(id: number): Promise<UserRow> {
  const response = await apiRequest<ApiResponse<UserRow>>(`/users/${id}`, { method: 'DELETE' });
  return response.data;
}
