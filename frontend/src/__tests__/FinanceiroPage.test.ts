import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../layouts/BaseLayout', () => ({ createBaseLayout: ({ content }: { content: HTMLElement }) => content }));
vi.mock('../components/InvoiceImportButton', () => ({ INVOICES_IMPORTED_EVENT: 'hub:invoices-imported' }));
vi.mock('../services/authService', () => ({ getCurrentUser: vi.fn() }));
const toast = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() }));
vi.mock('../hooks/useToast', () => ({ useToast: () => toast }));
vi.mock('../services/financeiroService', () => ({ getPendentesBoleto: vi.fn() }));
vi.mock('../services/billingCalculationsService', () => ({
  gerarBoletoConcessionaria: vi.fn(), calculateBillingInvoice: vi.fn(), downloadBillingInvoice: vi.fn()
}));
vi.mock('../pages/financeiroBoletoPanel', () => ({ openBoletoPanel: vi.fn() }));

import { ApiRequestError } from '../services/apiClient';
import { getCurrentUser } from '../services/authService';
import { getPendentesBoleto, type PendenteBoleto } from '../services/financeiroService';
import { calculateBillingInvoice, gerarBoletoConcessionaria } from '../services/billingCalculationsService';
import { openBoletoPanel } from '../pages/financeiroBoletoPanel';
import { createFinanceiroPage } from '../pages/FinanceiroPage';

async function flush(): Promise<void> { for (let i = 0; i < 10; i++) await Promise.resolve(); }

const item = (over: Partial<PendenteBoleto> = {}): PendenteBoleto => ({
  invoiceId: 10, clienteId: 1, clienteNome: 'Cliente Um', ucId: 7, ucCodigo: 'UC-1', competencia: '2026-01',
  dataVencimento: '2026-02-10', valorConcessionaria: '150.00', valorHub: '90.00', valorCobrar: '240.00',
  billingMode: 'unified', emissaoPendente: false, bloqueio: null, ...over
});
const groups = [
  { usinaId: 1, usinaNome: 'Usina A', itens: [item(), item({ invoiceId: 11, clienteNome: 'Cliente Dois', ucCodigo: 'UC-2' })] },
  { usinaId: null, usinaNome: null, itens: [item({ invoiceId: 12, clienteNome: 'Cliente Tres', billingMode: null, valorCobrar: null })] }
];
const btn = (root: ParentNode, text: string) =>
  Array.from(root.querySelectorAll('button')).find((b) => b.textContent === text) as HTMLButtonElement | undefined;
const one = (over: Partial<PendenteBoleto>) => [{ usinaId: 1, usinaNome: 'Usina A', itens: [item(over)] }];

describe('FinanceiroPage', () => {
  beforeEach(() => {
    window.dispatchEvent(new PopStateEvent('popstate'));
    vi.clearAllMocks();
    window.history.replaceState({}, '', '/');
    vi.mocked(getCurrentUser).mockReturnValue({ id: 1, role: 'owner' } as never);
    vi.mocked(getPendentesBoleto).mockResolvedValue(groups);
  });

  it('renders one block per usina with counts and Sem usina', async () => {
    const page = createFinanceiroPage();
    await flush();
    expect(Array.from(page.querySelectorAll('h2')).map((h) => h.textContent)).toEqual(['Usina A', 'Sem usina']);
    expect(page.textContent).toContain('2 clientes aguardando boleto');
    expect(page.textContent).toContain('1 cliente aguardando boleto');
    expect(page.querySelectorAll('table')[0].getAttribute('aria-label')).toContain('Usina A');
    expect(page.textContent).toContain('Unificada');
    expect(page.textContent).toContain('—');
  });

  it('shows the bloqueio message and disables Gerar boleto', async () => {
    vi.mocked(getPendentesBoleto).mockResolvedValue(one({ valorCobrar: null, bloqueio: { code: 'RULE_MISSING', message: 'Cliente sem regra de cobrança.' } }));
    const page = createFinanceiroPage();
    await flush();
    expect(page.textContent).toContain('Cliente sem regra de cobrança.');
    expect(btn(page, 'Gerar boleto')?.disabled).toBe(true);
    expect(btn(page, 'Calcular')).toBeUndefined();
  });

  it('NOT_CALCULATED shows Calcular, which recalculates and reloads', async () => {
    vi.mocked(getPendentesBoleto).mockResolvedValue(one({ bloqueio: { code: 'NOT_CALCULATED', message: 'Fatura ainda não calculada.' } }));
    vi.mocked(calculateBillingInvoice).mockResolvedValue({} as never);
    const page = createFinanceiroPage();
    await flush();
    btn(page, 'Calcular')?.click();
    await flush();
    expect(calculateBillingInvoice).toHaveBeenCalledWith(10, undefined);
    expect(toast.success).toHaveBeenCalled();
    expect(getPendentesBoleto).toHaveBeenCalledTimes(2);
  });

  it('emissaoPendente keeps the button enabled as Retomar emissão and shows the value', async () => {
    vi.mocked(getPendentesBoleto).mockResolvedValue(one({ emissaoPendente: true, bloqueio: { code: 'X', message: 'Bloqueio qualquer.' } }));
    const page = createFinanceiroPage();
    await flush();
    expect(btn(page, 'Retomar emissão')?.disabled).toBe(false);
    expect(page.textContent).not.toContain('Bloqueio qualquer.');
    expect(page.textContent).toContain('240,00');
  });

  it('Gerar boleto calls the service, opens the panel and reloads on close', async () => {
    vi.mocked(gerarBoletoConcessionaria).mockResolvedValue({ id: 99, valor: '240.00', mesVencimento: '2026-02-10', billingMode: 'unified' } as never);
    const page = createFinanceiroPage();
    await flush();
    btn(page, 'Gerar boleto')?.click();
    await flush();
    expect(gerarBoletoConcessionaria).toHaveBeenCalledWith(10, undefined);
    expect(toast.success.mock.calls[0][0]).toContain('Boleto gerado para Cliente Um');
    expect(openBoletoPanel).toHaveBeenCalledTimes(1);
    const opts = vi.mocked(openBoletoPanel).mock.calls[0][1];
    expect(opts.invoiceId).toBe(10);
    opts.onClose();
    await flush();
    expect(getPendentesBoleto).toHaveBeenCalledTimes(2);
  });

  it('shows the backend message literally on error and re-enables', async () => {
    vi.mocked(gerarBoletoConcessionaria).mockRejectedValue(new ApiRequestError(400, 'Cliente sem email cadastrado.'));
    const page = createFinanceiroPage();
    await flush();
    btn(page, 'Gerar boleto')?.click();
    await flush();
    expect(toast.error).toHaveBeenCalledWith('Cliente sem email cadastrado.');
    expect(openBoletoPanel).not.toHaveBeenCalled();
    expect(btn(page, 'Gerar boleto')?.disabled).toBe(false);
  });

  it('appends stage and blockers for BILLING_CALCULATION_REQUIRED', async () => {
    vi.mocked(gerarBoletoConcessionaria).mockRejectedValue(new ApiRequestError(422, 'Cálculo pendente.', 'BILLING_CALCULATION_REQUIRED', { stage: 'RULE_RESOLUTION', blockers: ['NO_RULE_CONFIGURED'] }));
    const page = createFinanceiroPage();
    await flush();
    btn(page, 'Gerar boleto')?.click();
    await flush();
    const message = toast.error.mock.calls[0][0] as string;
    expect(message).toContain('Cálculo pendente.');
    expect(message).toContain('RULE_RESOLUTION');
    expect(message).toContain('NO_RULE_CONFIGURED');
  });

  it('gear button navigates to the UC screen', async () => {
    const page = createFinanceiroPage();
    await flush();
    (page.querySelector('button[aria-label^="Configurar regra de cobrança"]') as HTMLButtonElement).click();
    expect(window.location.pathname + window.location.search).toBe('/ucs?ucId=7');
  });

  it('shows the empty state', async () => {
    vi.mocked(getPendentesBoleto).mockResolvedValueOnce([]);
    const page = createFinanceiroPage();
    await flush();
    expect(page.textContent).toContain('Nenhum cliente aguardando boleto.');
  });

  it('shows the error state with retry', async () => {
    vi.mocked(getPendentesBoleto).mockRejectedValueOnce(new Error('offline'));
    const page = createFinanceiroPage();
    await flush();
    expect(toast.error).toHaveBeenCalledWith('offline');
    btn(page, 'Tentar novamente')?.click();
    await flush();
    expect(page.textContent).toContain('Usina A');
  });

  it('reloads when invoices are imported', async () => {
    createFinanceiroPage();
    await flush();
    window.dispatchEvent(new Event('hub:invoices-imported'));
    await flush();
    expect(getPendentesBoleto).toHaveBeenCalledTimes(2);
  });

  it('platform admin without an empresa sees select-company and no API call', async () => {
    vi.mocked(getCurrentUser).mockReturnValue({ id: 1, isPlatformAdmin: true, platformViewEmpresaId: null } as never);
    const page = createFinanceiroPage();
    await flush();
    expect(getPendentesBoleto).not.toHaveBeenCalled();
    expect(page.textContent).toContain('Selecione uma empresa.');
  });

  it('platform admin in the test empresa lists groups and issues with the empresaId', async () => {
    vi.mocked(getCurrentUser).mockReturnValue({ id: 1, isPlatformAdmin: true, platformViewEmpresaId: 1 } as never);
    vi.mocked(gerarBoletoConcessionaria).mockResolvedValue({ id: 99, valor: '240.00', mesVencimento: '2026-02-10', billingMode: 'unified' } as never);
    const page = createFinanceiroPage();
    await flush();
    expect(page.textContent).toContain('Usina A');
    btn(page, 'Gerar boleto')?.click();
    await flush();
    expect(gerarBoletoConcessionaria).toHaveBeenCalledWith(10, 1);
    expect(vi.mocked(openBoletoPanel).mock.calls[0][1].empresaId).toBe(1);
    expect(btn(page, 'Gerar boleto')?.disabled).toBe(true);
  });

  it.each([
    ['platform admin in another empresa', { id: 1, isPlatformAdmin: true, platformViewEmpresaId: 2 }],
    ['tenant viewer', { id: 1, role: 'viewer' }]
  ])('%s sees the list without issuing buttons', async (_name, user) => {
    vi.mocked(getCurrentUser).mockReturnValue(user as never);
    const page = createFinanceiroPage();
    await flush();
    expect(page.textContent).toContain('Usina A');
    expect(btn(page, 'Gerar boleto')).toBeUndefined();
    expect(btn(page, 'Retomar emissão')).toBeUndefined();
    expect(page.querySelector('button[aria-label^="Configurar regra de cobrança"]')).not.toBeNull();
  });
});
