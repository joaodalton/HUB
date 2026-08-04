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

const USER_KEY = 'hub.auth.user';

export function isAuthenticated(): boolean {
  return Boolean(getToken());
}

// Cache leve do usuario logado (sessionStorage, mesmo padrao do tokenStorage.ts)
// -- so pra tela poder mostrar quem esta logado (ex.: cartao no rodape da
// sidebar) sem precisar de uma rota GET /auth/me, que ainda nao existe.
export function getCurrentUser(): AuthUser | null {
  const raw = window.sessionStorage.getItem(USER_KEY);
  if (!raw) return null;

  try {
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

export async function login(email: string, senha: string): Promise<AuthUser> {
  const response = await apiRequest<LoginEnvelope>('/auth/login', {
    method: 'POST',
    body: { email, senha }
  });

  setToken(response.data.token);
  window.sessionStorage.setItem(USER_KEY, JSON.stringify(response.data.user));
  return response.data.user;
}

export function logout(): void {
  clearToken();
  window.sessionStorage.removeItem(USER_KEY);
}