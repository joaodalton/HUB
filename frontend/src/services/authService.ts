import { apiRequest } from './apiClient';
import { clearToken, getToken, setToken } from './tokenStorage';

export type AuthUser = {
  id: number;
  email: string;
  papel: string;
  ativo: boolean;
};

type LoginEnvelope = {
  success: boolean;
  message: string;
  data: {
    token: string;
    user: AuthUser;
  };
};

export function isAuthenticated(): boolean {
  return Boolean(getToken());
}

export async function login(email: string, senha: string): Promise<AuthUser> {
  const response = await apiRequest<LoginEnvelope>('/auth/login', {
    method: 'POST',
    body: { email, senha }
  });

  setToken(response.data.token);
  return response.data.user;
}

export function logout(): void {
  clearToken();
}