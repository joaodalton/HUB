import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../layouts/BaseLayout', () => ({
  createBaseLayout: ({ content }: { content: HTMLElement }) => content,
}));

vi.mock('../components/ConcessionariaInvoicesPanel', () => ({
  createConcessionariaUploadButton: () => null,
}));

vi.mock('../pages/faturasInvoiceDetail', () => ({
  createFaturaInvoiceDetail: vi.fn(),
}));

vi.mock('../services/authService', () => ({
  getCurrentUser: vi.fn(),
}));

vi.mock('../services/billingCalculationsService', () => ({
  getBillingInvoicePage: vi.fn(),
  downloadBillingInvoice: vi.fn(),
}));

vi.mock('../services/faturasService', () => ({
  getFaturas: vi.fn(),
  createFatura: vi.fn(),
}));

vi.mock('../services/pendenciasService', () => ({
  getPendencias: vi.fn(),
}));

vi.mock('../services/clientsService', () => ({
  getClients: vi.fn(),
}));

vi.mock('../services/ucsService', () => ({
  getUcs: vi.fn(),
}));

import { getCurrentUser } from '../services/authService';
import { getBillingInvoicePage } from '../services/billingCalculationsService';
import { getFaturas } from '../services/faturasService';
import { getPendencias } from '../services/pendenciasService';
import { getClients } from '../services/clientsService';
import { getUcs } from '../services/ucsService';
import { createFaturaInvoiceDetail } from '../pages/faturasInvoiceDetail';
import { createFaturasPage } from '../pages/FaturasPage';

async function flush(): Promise<void> {
  await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
}

const owner = { id: 1, empresaId: 1, nome: 'Owner', email: 'owner@hub.com', role: 'owner', status: 'ativo', mustChangePassword: false };

const invoice = {
  id: 10, clientId: 1, consumerUnitId: 1, competencia: '2026-01',
  statusExtracao: 'extraida', statusValidacao: 'valida', createdAt: '2026-01-01',
  clienteNome: 'Cliente Um', ucCodigo: 'UC-1', usinas: [{ id: 1, nome: 'Usina A' }],
  valorTotalConcessionaria: '150.00', dataVencimento: '2026-01-10',
  documentoDisponivel: false, temPendencia: false
};

function stubInvoicePage(data: typeof invoice[] = [invoice]) {
  vi.mocked(getBillingInvoicePage).mockResolvedValue({ data, pagination: { page: 1, pageSize: 25, total: data.length, pages: 1 } });
}

describe('FaturasPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.history.replaceState({}, '', '/');
    vi.mocked(getCurrentUser).mockReturnValue(owner as never);
    vi.mocked(getFaturas).mockResolvedValue([]);
    vi.mocked(getPendencias).mockResolvedValue([]);
    vi.mocked(getClients).mockResolvedValue([]);
    vi.mocked(getUcs).mockResolvedValue([]);
  });
  afterEach(() => { vi.restoreAllMocks(); });

  it('renders one row per invoice when ready', async () => {
    stubInvoicePage();
    const content = createFaturasPage();
    await flush();
    expect(getBillingInvoicePage).toHaveBeenCalledTimes(1);
    expect(content.textContent).toContain('Cliente Um');
    expect(content.textContent).toContain('UC-1');
  });

  it('shows the empty state when there are no invoices', async () => {
    stubInvoicePage([]);
    const content = createFaturasPage();
    await flush();
    expect(content.textContent).toContain('Nenhuma fatura encontrada');
  });

  it('shows an error state when loading fails', async () => {
    vi.mocked(getBillingInvoicePage).mockRejectedValue(new Error('network down'));
    const content = createFaturasPage();
    await flush();
    expect(content.textContent).toContain('Nao foi possivel carregar as faturas');
  });

  it('opens the invoice detail when a row is clicked', async () => {
    stubInvoicePage();
    const content = createFaturasPage();
    await flush();
    const row = content.querySelector('tbody tr');
    expect(row).not.toBeNull();
    row?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flush();
    expect(createFaturaInvoiceDetail).toHaveBeenCalledTimes(1);
    expect(vi.mocked(createFaturaInvoiceDetail).mock.calls[0][0]).toMatchObject({ id: invoice.id });
  });
});

describe('FaturasPage - exceção de teste para platform admin', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.history.replaceState({}, '', '/');
    stubInvoicePage([]);
    vi.mocked(getFaturas).mockResolvedValue([]);
    vi.mocked(getPendencias).mockResolvedValue([]);
    vi.mocked(getClients).mockResolvedValue([]);
    vi.mocked(getUcs).mockResolvedValue([]);
  });
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
