import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../services/authService', () => ({ clearSession: vi.fn() }));
import { clearSession } from '../services/authService';
import { ApiRequestError, NetworkError, apiRequest, apiUpload } from '../services/apiClient';

function mockFetch(status: number, body: unknown, headers: Record<string, string> = {}): ReturnType<typeof vi.fn> {
  const fn = vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json', ...headers } })));
  vi.stubGlobal('fetch', fn);
  return fn;
}

describe('apiClient', () => {
  beforeEach(() => { document.cookie = 'hub_csrf=token-xyz'; window.history.replaceState({}, '', '/clientes'); });
  afterEach(() => { vi.unstubAllGlobals(); });

  it('envia cookie de sessao e X-CSRF-Token so em metodos mutantes', async () => {
    const fetchSpy = mockFetch(200, { data: 1 });
    await apiRequest('/clients');
    let [, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect(init.credentials).toBe('include');
    expect((init.headers as Record<string, string>)['X-CSRF-Token']).toBeUndefined();

    await apiRequest('/clients', { method: 'POST', body: { nome: 'x' } });
    [, init] = fetchSpy.mock.calls[1] as [string, RequestInit];
    expect((init.headers as Record<string, string>)['X-CSRF-Token']).toBe('token-xyz');
    expect(init.body).toBe('{"nome":"x"}');
  });

  it('upload multipart tambem leva CSRF e nao forca Content-Type', async () => {
    const fetchSpy = mockFetch(201, { data: null });
    await apiUpload('/documents', new FormData());
    const [, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect((init.headers as Record<string, string>)['X-CSRF-Token']).toBe('token-xyz');
    expect((init.headers as Record<string, string>)['Content-Type']).toBeUndefined();
  });

  it('401 limpa a sessao e redireciona para /login', async () => {
    mockFetch(401, { error: 'nao autenticado' });
    await expect(apiRequest('/clients')).rejects.toBeInstanceOf(ApiRequestError);
    expect(clearSession).toHaveBeenCalled();
    expect(window.location.pathname).toBe('/login');
  });

  it('erro da API vira ApiRequestError com a mensagem do backend', async () => {
    mockFetch(400, { error: 'CPF invalido' });
    await expect(apiRequest('/clients', { method: 'POST', body: {} })).rejects.toMatchObject({ status: 400, message: 'CPF invalido' });
  });

  it('403 PASSWORD_CHANGE_REQUIRED dispara o evento global', async () => {
    mockFetch(403, { code: 'PASSWORD_CHANGE_REQUIRED', error: 'troca obrigatoria' });
    const listener = vi.fn();
    window.addEventListener('hub:password-change-required', listener);
    await expect(apiRequest('/clients')).rejects.toBeInstanceOf(ApiRequestError);
    expect(listener).toHaveBeenCalledTimes(1);
  });

  it('falha de rede vira NetworkError em vez de TypeError cru', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
    await expect(apiRequest('/clients')).rejects.toBeInstanceOf(NetworkError);
  });
});
