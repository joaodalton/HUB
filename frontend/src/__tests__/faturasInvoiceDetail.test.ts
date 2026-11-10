import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../services/billingCalculationsService', async () => {
  const actual = await vi.importActual<typeof import('../services/billingCalculationsService')>('../services/billingCalculationsService');
  return {
    ...actual,
    getBillingExecutions: vi.fn().mockResolvedValue([]),
    getBillingExecution: vi.fn(),
    gerarBoletoConcessionaria: vi.fn(),
  };
});

vi.mock('../services/faturasService', async () => {
  const actual = await vi.importActual<typeof import('../services/faturasService')>('../services/faturasService');
  return { ...actual, cancelFatura: vi.fn(), syncFatura: vi.fn() };
});

import { gerarBoletoConcessionaria, type BillingInvoice } from '../services/billingCalculationsService';
import { cancelFatura, type FaturaRow } from '../services/faturasService';
import { createFaturaInvoiceDetail } from '../pages/faturasInvoiceDetail';

function baseInvoice(overrides: Partial<BillingInvoice> = {}): BillingInvoice {
  return {
    id: 10,
    clientId: 1,
    consumerUnitId: 5,
    competencia: '2026-09',
    statusExtracao: 'extraida',
    statusValidacao: 'valida',
    createdAt: '2026-09-01T00:00:00Z',
    clienteNome: 'Cliente Teste',
    ucCodigo: 'UC-1',
    usinas: [],
    valorTotalConcessionaria: '150.00',
    dataVencimento: '2026-10-10',
    documentoId: 1,
    documentoDisponivel: false,
    temPendencia: false,
    gdIKwh: null,
    gdIIKwh: null,
    problemas: [],
    ...overrides,
  };
}

function baseCharge(overrides: Partial<FaturaRow> = {}): FaturaRow {
  return {
    id: 50, clienteId: 1, clienteNome: 'Cliente Teste', ucId: 5, ucCodigo: 'UC-1',
    concessionaria: 'Copel', competencia: '2026-09', valor: '150.00', mesVencimento: '2026-10-10',
    origem: 'automatica', asaasId: 'pay_1', statusInterno: 'emitida', paymentProvider: 'asaas',
    externalReference: null, asaasStatus: 'pending', boletoUrl: null, linhaDigitavel: null,
    codigoBarras: null, enviadoEm: null, criadoEm: null,
    billingMode: null, invoiceUrl: null, faturaConcessionariaId: null, ...overrides,
  };
}

function render(invoice: BillingInvoice, _unused: unknown, opts: {
  toast?: { success: ReturnType<typeof vi.fn>; error: ReturnType<typeof vi.fn> };
  reload?: ReturnType<typeof vi.fn>;
  charges?: FaturaRow[];
  canIssue?: boolean;
  isPlatformAdmin?: boolean;
  empresaId?: number;
} = {}) {
  const toast = opts.toast ?? { success: vi.fn(), error: vi.fn() };
  const reload = opts.reload ?? vi.fn().mockResolvedValue(undefined);
  const content = document.createElement('div');
  createFaturaInvoiceDetail(invoice, {
    content,
    clients: [],
    isPlatformAdmin: opts.isPlatformAdmin ?? false,
    canIssue: opts.canIssue ?? true,
    empresaId: opts.empresaId,
    contextualCharges: () => opts.charges ?? [],
    relatedPendencias: () => [],
    invoiceDownloadButton: () => document.createElement('button'),
    getSelectedInvoiceId: () => invoice.id,
    reload,
    toast,
    onClose: vi.fn(),
  });
  const buttons = Array.from(content.querySelectorAll('button'));
  const excluirButton = buttons.find((item) => item.textContent === 'Excluir boleto') as HTMLButtonElement | undefined;
  return { content, excluirButton, toast, reload };
}

describe('faturasInvoiceDetail - atalho Gerar boleto no Financeiro', () => {
  beforeEach(() => { vi.clearAllMocks(); });
  afterEach(() => { vi.restoreAllMocks(); });

  it('sem boleto mostra o atalho que navega para /financeiro e nao emite', () => {
    const popstate = vi.fn();
    window.addEventListener('popstate', popstate);
    const { content } = render(baseInvoice(), () => true);
    expect(Array.from(content.querySelectorAll('button')).some((item) => item.textContent === 'Gerar boleto')).toBe(false);
    const link = Array.from(content.querySelectorAll('button')).find((item) => item.textContent === 'Gerar boleto no Financeiro')!;
    link.click();
    expect(window.location.pathname).toBe('/financeiro');
    expect(popstate).toHaveBeenCalledTimes(1);
    expect(gerarBoletoConcessionaria).not.toHaveBeenCalled();
    window.removeEventListener('popstate', popstate);
  });

  it('com boleto ou sem permissao o atalho nao aparece', () => {
    const withBoleto = baseInvoice({ contextualCharges: [{ id: 1, statusInterno: 'emitida', asaasStatus: 'pending', asaasId: 'pay_1', valor: 150, mesVencimento: '2026-10-10', boletoUrl: null, invoiceUrl: null, billingMode: null }] });
    expect(render(withBoleto, () => true).content.textContent).not.toContain('Gerar boleto no Financeiro');
    expect(render(baseInvoice(), () => true, { canIssue: false }).content.textContent).not.toContain('Gerar boleto no Financeiro');
  });
});

describe('faturasInvoiceDetail - botao Excluir boleto', () => {
  beforeEach(() => { vi.clearAllMocks(); });
  afterEach(() => { vi.restoreAllMocks(); });

  it('nao aparece quando nao ha cobranca ASAAS pendente vinculada', () => {
    const { excluirButton } = render(baseInvoice(), () => true, { charges: [baseCharge({ asaasStatus: 'received' })] });
    expect(excluirButton).toBeUndefined();
  });

  it('nao aparece sem permissao (canIssue false), mesmo com cobranca pendente', () => {
    const { excluirButton } = render(baseInvoice(), () => true, { charges: [baseCharge()], canIssue: false });
    expect(excluirButton).toBeUndefined();
  });

  it('aparece quando ha cobranca pendente com asaasId vinculada', () => {
    const { excluirButton } = render(baseInvoice(), () => true, { charges: [baseCharge()] });
    expect(excluirButton).toBeInstanceOf(HTMLButtonElement);
  });

  it('cancela a selecionado confirmando: chama cancelFatura, toast de sucesso e reload', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    vi.mocked(cancelFatura).mockResolvedValue({} as FaturaRow);
    const { excluirButton, toast, reload } = render(baseInvoice(), () => true, { charges: [baseCharge({ id: 77 })] });
    excluirButton!.click();
    await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
    expect(cancelFatura).toHaveBeenCalledWith(77);
    expect(toast.success).toHaveBeenCalledWith('Cobrança cancelada.');
    expect(reload).toHaveBeenCalledTimes(1);
  });

  it('nao cancela se o usuario recusar a confirmacao', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false);
    const { excluirButton } = render(baseInvoice(), () => true, { charges: [baseCharge()] });
    excluirButton!.click();
    await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
    expect(cancelFatura).not.toHaveBeenCalled();
  });
});
