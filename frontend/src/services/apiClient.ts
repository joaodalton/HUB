import { config } from './config';
import { clearSession } from './authService';

type RequestOptions = Omit<RequestInit, 'body'> & {
  body?: unknown;
};

const CSRF_COOKIE_NAME = 'hub_csrf';
const MUTATING_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

function readCsrfCookie(): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${CSRF_COOKIE_NAME}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

function buildCsrfHeader(method: string | undefined): HeadersInit {
  const normalizedMethod = (method ?? 'GET').toUpperCase();
  if (!MUTATING_METHODS.has(normalizedMethod)) return {};
  const csrfToken = readCsrfCookie();
  return csrfToken ? { 'X-CSRF-Token': csrfToken } : {};
}

function buildJsonHeaders(method: string | undefined, extra?: HeadersInit): HeadersInit {
  return { 'Content-Type': 'application/json', ...buildCsrfHeader(method), ...extra };
}

function redirectToLogin(): void {
  clearSession();
  if (window.location.pathname !== '/login') {
    window.history.pushState({}, '', '/login');
    window.dispatchEvent(new PopStateEvent('popstate'));
  }
}

async function readErrorMessage(response: Response): Promise<string> {
  const payload = await response.json().catch(() => null) as { message?: string; error?: string } | null;
  return payload?.message ?? payload?.error ?? 'Falha na comunicacao com a API.';
}

async function notifyRequiredPasswordChange(response: Response): Promise<void> {
  if (response.status !== 403) return;
  const payload = await response.clone().json().catch(() => null) as { code?: string; errorCode?: string; message?: string } | null;
  const code = payload?.code ?? payload?.errorCode ?? '';
  const message = payload?.message ?? '';
  if (code === 'PASSWORD_CHANGE_REQUIRED' || /troca.*senha|senha.*obrigat|password.*change/i.test(message)) {
    window.dispatchEvent(new Event('hub:password-change-required'));
  }
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await fetch(`${config.apiBaseUrl}${config.apiPrefix}${path}`, {
    ...options,
    credentials: 'include',
    headers: buildJsonHeaders(options.method, options.headers),
    body: options.body ? JSON.stringify(options.body) : undefined
  });

  if (response.status === 401) redirectToLogin();
  await notifyRequiredPasswordChange(response);
  if (!response.ok) throw new Error(await readErrorMessage(response));
  return response.json() as Promise<T>;
}

export async function apiBlob(path: string, options: RequestOptions = {}): Promise<Blob> {
  const response = await fetch(`${config.apiBaseUrl}${config.apiPrefix}${path}`, {
    ...options,
    credentials: 'include',
    headers: buildJsonHeaders(options.method, options.headers),
    body: options.body ? JSON.stringify(options.body) : undefined
  });

  if (response.status === 401) redirectToLogin();
  await notifyRequiredPasswordChange(response);
  if (!response.ok) throw new Error(await readErrorMessage(response));
  return response.blob();
}

export async function apiUpload<T>(path: string, formData: FormData): Promise<T> {
  const response = await fetch(`${config.apiBaseUrl}${config.apiPrefix}${path}`, {
    method: 'POST',
    credentials: 'include',
    headers: buildCsrfHeader('POST'),
    body: formData
  });

  if (response.status === 401) redirectToLogin();
  await notifyRequiredPasswordChange(response);
  if (!response.ok) throw new Error(await readErrorMessage(response));
  return response.json() as Promise<T>;
}
