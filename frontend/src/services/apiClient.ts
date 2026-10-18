import { config } from './config';
import { clearSession } from './authService';

type RequestOptions = Omit<RequestInit, 'body'> & {
  body?: unknown;
};

const CSRF_COOKIE_NAME = 'hub_csrf';
const MUTATING_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

export class ApiRequestError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
    this.name = 'ApiRequestError';
  }
}

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

/** Resposta padrao do backend (utils/api_response.py). Unica declaracao: os
 *  services importam daqui em vez de redeclarar (30 copias divergentes antes). */
export type ApiResponse<T> = { success?: boolean; message?: string; data: T };

export class NetworkError extends ApiRequestError {
  constructor(public readonly reason: unknown) {
    super(0, 'Sem conexao com o servidor. Verifique sua internet e tente de novo.');
    this.name = 'NetworkError';
  }
}

async function execute(path: string, init: RequestInit): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(`${config.apiBaseUrl}${config.apiPrefix}${path}`, { ...init, credentials: 'include' });
  } catch (cause) {
    throw new NetworkError(cause);
  }
  if (response.status === 401) redirectToLogin();
  await notifyRequiredPasswordChange(response);
  if (!response.ok) throw new ApiRequestError(response.status, await readErrorMessage(response));
  return response;
}

function jsonInit(options: RequestOptions): RequestInit {
  return { ...options, headers: buildJsonHeaders(options.method, options.headers), body: options.body ? JSON.stringify(options.body) : undefined };
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  return (await execute(path, jsonInit(options))).json() as Promise<T>;
}

export async function apiBlob(path: string, options: RequestOptions = {}): Promise<Blob> {
  return (await apiBlobWithHeaders(path, options)).blob;
}

export async function apiBlobWithHeaders(path: string, options: RequestOptions = {}): Promise<{ blob: Blob; contentDisposition: string | null }> {
  const response = await execute(path, jsonInit(options));
  return { blob: await response.blob(), contentDisposition: response.headers.get('Content-Disposition') };
}

export async function apiUpload<T>(path: string, formData: FormData): Promise<T> {
  const response = await execute(path, { method: 'POST', headers: buildCsrfHeader('POST'), body: formData });
  return response.json() as Promise<T>;
}
