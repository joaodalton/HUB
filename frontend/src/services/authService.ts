import { apiRequest } from './apiClient';

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
};

type ApiResponse<T> = {
  success: boolean;
  message: string;
  data: T;
};

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
  } catch {
    cachedUser = null;
  }
  sessionChecked = true;
  return cachedUser;
}

export async function refreshCurrentUser(): Promise<AuthUser | null> {
  try {
    const response = await apiRequest<ApiResponse<AuthUser>>('/auth/me');
    cachedUser = response.data;
  } catch {
    cachedUser = null;
  }
  sessionChecked = true;
  return cachedUser;
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
