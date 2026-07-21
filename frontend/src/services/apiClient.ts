import { config } from './config';
import { clearToken, getToken } from './tokenStorage';

type RequestOptions = Omit<RequestInit, 'body'> & {
  body?: unknown;
};

function buildHeaders(extra?: HeadersInit): HeadersInit {
  const token = getToken();

  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...extra
  };
}

function redirectToLogin(): void {
  clearToken();

  if (window.location.pathname !== '/login') {
    window.history.pushState({}, '', '/login');
    window.dispatchEvent(new PopStateEvent('popstate'));
  }
}

async function readErrorMessage(response: Response): Promise<string> {
  const payload = await response.json().catch(() => null) as { message?: string; error?: string } | null;
  return payload?.message ?? payload?.error ?? 'Falha na comunicacao com a API.';
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await fetch(`${config.apiBaseUrl}${path}`, {
    ...options,
    headers: buildHeaders(options.headers),
    body: options.body ? JSON.stringify(options.body) : undefined
  });

  if (response.status === 401) {
    redirectToLogin();
  }

  if (!response.ok) {
    throw new Error(await readErrorMessage(response));
  }

  return response.json() as Promise<T>;
}

export async function apiBlob(path: string, options: RequestOptions = {}): Promise<Blob> {
  const response = await fetch(`${config.apiBaseUrl}${path}`, {
    ...options,
    headers: buildHeaders(options.headers),
    body: options.body ? JSON.stringify(options.body) : undefined
  });

  if (response.status === 401) {
    redirectToLogin();
  }

  if (!response.ok) {
    throw new Error(await readErrorMessage(response));
  }

  return response.blob();
}