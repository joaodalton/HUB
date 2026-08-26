import { apiRequest } from './apiClient';

export type AuthUser = {
  id: number;
  empresaId: number;
  nome: string;
  email: string;
  role: string;
  status: string;
  empresaNome?: string | null;
  isPlatformAdmin?: boolean;
  platformView?: { empresaId: number; empresaNome: string } | null;
  platformViewEmpresaId?: number | null;
  platformViewEmpresaNome?: string | null;
  homeEmpresaId?: number;
};

type ApiResponse<T> = { success: boolean; message: string; data: T };

let cachedUser: AuthUser | null = null;
let sessionChecked = false;

export function isAuthenticated(): boolean {
  return cachedUser !== null;
}

export function getCurrentUser(): AuthUser | null {
  return cachedUser;
}

export async function ensureSession(): Promise<AuthUser | null> {
  if (sessionChecked) return cachedUser;
  try {
    const response = await apiRequest<ApiResponse<AuthUser>>('/auth/me');
    cachedUser = response.data;
    sessionChecked = true;
    return cachedUser;
  } catch {
    cachedUser = null;
    sessionChecked = true;
    return null;
  }
}

export function clearSession(): void {
  cachedUser = null;
  sessionChecked = true;
}

export async function login(email: string, senha: string, lembrar = false): Promise<AuthUser> {
  const response = await apiRequest<ApiResponse<AuthUser>>('/auth/login', {
    method: 'POST',
    body: { email, senha, lembrar }
  });
  cachedUser = response.data;
  sessionChecked = true;
  return response.data;
}

export async function logout(): Promise<void> {
  try {
    await apiRequest('/auth/logout', { method: 'POST' });
  } catch {
    // ignora
  }
  clearSession();
}

export async function register(email: string, senha: string, codigo: string): Promise<void> {
  await apiRequest('/auth/register', {
    method: 'POST',
    body: { email, senha, codigo }
  });
}
