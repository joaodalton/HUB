import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../layouts/BaseLayout', () => ({
  createBaseLayout: ({ content }: { content: HTMLElement }) => content,
}));

vi.mock('../services/authService', () => ({
  getCurrentUser: vi.fn(),
}));

vi.mock('../services/billingCalculationsService', async () => {
  const actual = await vi.importActual<typeof import('../services/billingCalculationsService')>('../services/billingCalculationsService');
  return {
    ...actual,
    getBillingInvoicePage: vi.fn().mockResolvedValue({ data: [], pagination: { page: 1, pageSize: 25, total: 0, pages: 0 } }),
    downloadBillingInvoice: vi.fn(),
  };
});

vi.mock('../services/faturasService', async () => {
  const actual = await vi.importActual<typeof import('../services/faturasService')>('../services/faturasService');
  return { ...actual, getFaturas: vi.fn().mockResolvedValue([]), createFatura: vi.fn() };
});

vi.mock('../services/pendenciasService', async () => {
  const actual = await vi.importActual<typeof import('../services/pendenciasService')>('../services/pendenciasService');
  return { ...actual, getPendencias: vi.fn().mockResolvedValue([]) };
});

vi.mock('../services/clientsService', async () => {
  const actual = await vi.importActual<typeof import('../services/clientsService')>('../services/clientsService');
  return { ...actual, getClients: vi.fn().mockResolvedValue([]) };
});

vi.mock('../services/ucsService', async () => {
  const actual = await vi.importActual<typeof import('../services/ucsService')>('../services/ucsService');
  return { ...actual, getUcs: vi.fn().mockResolvedValue([]) };
});

import { getCurrentUser } from '../services/authService';
import { getFaturas } from '../services/faturasService';
import { getPendencias } from '../services/pendenciasService';
import { getClients } from '../services/clientsService';
import { getUcs } from '../services/ucsService';
import { createFaturasPage } from '../pages/FaturasPage';

async function flush(): Promise<void> {
  await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
}

describe('FaturasPage - exceção de teste para platform admin', () => {
  beforeEach(() => { vi.clearAllMocks(); });
  afterEach(() => { vi.restoreAllMocks(); });

  it('platform admin na empresa de teste (id 1): canIssue true, emite cobrança e carrega os dados tenant-scoped', async () => {
    vi.mocked(getCurrentUser).mockReturnValue({ id: 1, nome: 'Admin', role: 'platform_admin', isPlatformAdmin: true, platformViewEmpresaId: 1 } as never);
    const content = createFaturasPage();
    await flush();
    expect(getFaturas).toHaveBeenCalledTimes(1);
    expect(getPendencias).toHaveBeenCalledTimes(1);
    expect(getClients).toHaveBeenCalledTimes(1);
    expect(getUcs).toHaveBeenCalledTimes(1);
    const emitir = Array.from(content.querySelectorAll('button')).find((button) => button.textContent?.includes('Emitir cobrança'));
    expect(emitir).toBeInstanceOf(HTMLButtonElement);
  });

  it('platform admin fora da empresa de teste: canIssue false, nao emite cobranca e nao carrega os dados tenant-scoped', async () => {
    vi.mocked(getCurrentUser).mockReturnValue({ id: 1, nome: 'Admin', role: 'platform_admin', isPlatformAdmin: true, platformViewEmpresaId: 2 } as never);
    const content = createFaturasPage();
    await flush();
    expect(getFaturas).not.toHaveBeenCalled();
    expect(getPendencias).not.toHaveBeenCalled();
    expect(getClients).not.toHaveBeenCalled();
    expect(getUcs).not.toHaveBeenCalled();
    const emitir = Array.from(content.querySelectorAll('button')).find((button) => button.textContent?.includes('Emitir cobrança'));
    expect(emitir).toBeUndefined();
  });
});
