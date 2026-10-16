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

import { ApiRequestError } from '../services/apiClient';
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
    ...overrides,
  };
}

function baseCharge(overrides: Partial<FaturaRow> = {}): FaturaRow {
  return {
    id: 50, clienteId: 1, clienteNome: 'Cliente Teste', ucId: 5, ucCodigo: 'UC-1',
    concessionaria: 'Copel', competencia: '2026-09', valor: '150.00', mesVencimento: '2026-10-10',
    origem: 'automatica', asaasId: 'pay_1', statusInterno: 'emitida', paymentProvider: 'asaas',
    externalReference: null, asaasStatus: 'pending', boletoUrl: null, linhaDigitavel: null,
    codigoBarras: null, enviadoEm: null, criadoEm: null, ...overrides,
  };
}

function render(invoice: BillingInvoice, canIssueInvoice: (invoice: BillingInvoice) => boolean, opts: {
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
    canIssueInvoice,
    openCreateModal: vi.fn(),
    getSelectedInvoiceId: () => invoice.id,
    reload,
    toast,
    onClose: vi.fn(),
  });
  const buttons = Array.from(content.querySelectorAll('button'));
  const button = buttons.find((item) => item.textContent === 'Gerar boleto') as HTMLButtonElement;
  const excluirButton = buttons.find((item) => item.textContent === 'Excluir boleto') as HTMLButtonElement | undefined;
  return { content, button, excluirButton, toast, reload };
}

describe('faturasInvoiceDetail - botao Gerar boleto', () => {
  beforeEach(() => { vi.clearAllMocks(); });
  afterEach(() => { vi.restoreAllMocks(); });

  it('fica desabilitado quando a fatura nao tem dados suficientes', () => {
    const { button } = render(baseInvoice(), () => false);
    expect(button.disabled).toBe(true);
    expect(button.dataset.tooltip).toBeTruthy();
  });

  it('ao clicar com sucesso chama o servico, mostra toast e recarrega', async () => {
    vi.mocked(gerarBoletoConcessionaria).mockResolvedValue({ id: 99 } as never);
    const { button, toast, reload } = render(baseInvoice(), () => true);
    expect(button.disabled).toBe(false);
    button.click();
    await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
    expect(gerarBoletoConcessionaria).toHaveBeenCalledWith(10, undefined);
    expect(toast.success).toHaveBeenCalledWith('Boleto gerado.');
    expect(reload).toHaveBeenCalledTimes(1);
  });

  it('platform admin testando empresa 1 chama o servico com o empresaId da rota de plataforma', async () => {
    vi.mocked(gerarBoletoConcessionaria).mockResolvedValue({ id: 99 } as never);
    const { button } = render(baseInvoice(), () => true, { isPlatformAdmin: true, empresaId: 1 });
    button.click();
    await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
    expect(gerarBoletoConcessionaria).toHaveBeenCalledWith(10, 1);
  });

  it('erro 422 INVOICE_DATA_INCOMPLETE lista os campos faltando traduzidos', async () => {
    vi.mocked(gerarBoletoConcessionaria).mockRejectedValue(
      new ApiRequestError(422, 'Dados incompletos.', 'INVOICE_DATA_INCOMPLETE', { missing: ['ucId', 'valor'] })
    );
    const { button, toast } = render(baseInvoice(), () => true);
    button.click();
    await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
    expect(toast.error).toHaveBeenCalledWith('Dados incompletos para gerar boleto: UC, valor da concessionária.');
    expect(button.disabled).toBe(false);
  });

  it('erro 409 EMISSAO_PENDENTE avisa que a emissao ja esta em andamento', async () => {
    vi.mocked(gerarBoletoConcessionaria).mockRejectedValue(
      new ApiRequestError(409, 'Emissao pendente.', 'EMISSAO_PENDENTE', { faturaId: 10 })
    );
    const { button, toast } = render(baseInvoice(), () => true);
    button.click();
    await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
    expect(toast.error).toHaveBeenCalledWith('Emissão deste boleto já está em andamento. Aguarde a conclusão.');
    expect(button.disabled).toBe(false);
  });

  it('erro generico (sem code) cai no fallback sem quebrar', async () => {
    vi.mocked(gerarBoletoConcessionaria).mockRejectedValue(new Error('Sem conexao com o servidor.'));
    const { button, toast } = render(baseInvoice(), () => true);
    button.click();
    await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
    expect(toast.error).toHaveBeenCalledWith('Sem conexao com o servidor.');
    expect(button.disabled).toBe(false);
  });

  it('impede duplo clique enquanto a chamada esta em voo', async () => {
    let resolveCall: (value: FaturaRow) => void = () => {};
    vi.mocked(gerarBoletoConcessionaria).mockImplementation(() => new Promise((resolve) => { resolveCall = resolve; }));
    const { button } = render(baseInvoice(), () => true);
    button.click();
    expect(button.disabled).toBe(true);
    button.click();
    resolveCall({ id: 99 } as FaturaRow);
    await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
    expect(gerarBoletoConcessionaria).toHaveBeenCalledTimes(1);
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
