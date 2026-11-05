import { apiRequest, type ApiResponse } from './apiClient';
import { getCachedUser, setCachedUser, isSessionChecked, clearSession } from './sessionState';

export type AuthUser = {
  id: number;
  empresaId: number;
  nome: string;
  email: string;
  role: string;
  status: string;
  mustChangePassword: boolean;
  empresaNome?: string | null;
  isPlatformAdmin?: boolean;
  isPlatformWorker?: boolean;
  platformViewEmpresaId?: number | null;
  platformViewEmpresaNome?: string | null;
  homeEmpresaId?: number;
};

export { clearSession };

export function isAuthenticated(): boolean {
  return getCachedUser() !== null;
}

export function getCurrentUser(): AuthUser | null {
  return getCachedUser();
}

export async function ensureSession(): Promise<AuthUser | null> {
  if (isSessionChecked()) return getCachedUser();
  try {
    const response = await apiRequest<ApiResponse<AuthUser>>('/auth/me');
    setCachedUser(response.data);
  } catch {
    setCachedUser(null);
  }
  return getCachedUser();
}

export async function refreshCurrentUser(): Promise<AuthUser | null> {
  try {
    const response = await apiRequest<ApiResponse<AuthUser>>('/auth/me');
    setCachedUser(response.data);
  } catch {
    setCachedUser(null);
  }
  return getCachedUser();
}

export async function login(email: string, senha: string, lembrar = false): Promise<AuthUser> {
  const response = await apiRequest<ApiResponse<AuthUser>>('/auth/login', {
    method: 'POST',
    body: { email, senha, lembrar }
  });
  setCachedUser(response.data);
  return response.data;
}

export async function alterarSenhaObrigatoria(senhaAtual: string, novaSenha: string): Promise<void> {
  await apiRequest<ApiResponse<unknown>>('/auth/alterar-senha', {
    method: 'POST',
    body: { senhaAtual, novaSenha }
  });
}

// Auto-cadastro (tela de login) -- so funciona se o backend tiver SIGNUP_CODE
// configurado e o codigo bater. NAO loga sozinho -- devolve so a confirmacao,
// quem chamou decide se quer logar em seguida (ver LoginPage.ts).
export async function register(email: string, senha: string, codigo: string): Promise<void> {
  await apiRequest('/auth/register', {
    method: 'POST',
    body: { email, senha, codigo }
  });
}

export async function logout(): Promise<void> {
  try {
    await apiRequest('/auth/logout', { method: 'POST' });
  } catch {
    // ignora -- limpa local mesmo assim
  }
  clearSession();
}
