import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../layouts/BaseLayout', () => ({
  createBaseLayout: ({ content }: { content: HTMLElement }) => content,
}));

vi.mock('../components/InvoiceImportButton', () => ({
  createInvoiceImportButton: () => null,
  INVOICES_IMPORTED_EVENT: 'hub:invoices-imported',
}));

vi.mock('../pages/faturasInvoiceDetail', () => ({
  createFaturaInvoiceDetail: vi.fn(),
}));

vi.mock('../services/authService', () => ({
  getCurrentUser: vi.fn(),
}));

const toast = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() }));
vi.mock('../hooks/useToast', () => ({ useToast: () => toast }));

vi.mock('../services/billingCalculationsService', () => ({
  getBillingInvoicePage: vi.fn(),
  downloadBillingInvoice: vi.fn(),
  deleteBillingInvoice: vi.fn(),
  reprocessBillingInvoice: vi.fn(),
}));

vi.mock('../services/faturasService', () => ({
  getFaturas: vi.fn(),
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

import { ApiRequestError } from '../services/apiClient';
import { deleteBillingInvoice, getBillingInvoicePage, reprocessBillingInvoice } from '../services/billingCalculationsService';
import { getCurrentUser } from '../services/authService';
import { getFaturas } from '../services/faturasService';
import { getPendencias } from '../services/pendenciasService';
import { getClients } from '../services/clientsService';
import { getUcs } from '../services/ucsService';
import { createFaturaInvoiceDetail } from '../pages/faturasInvoiceDetail';
import { createFaturasPage } from '../pages/FaturasPage';

async function flush(): Promise<void> {
  for (let i = 0; i < 8; i++) await Promise.resolve();
}

const owner = { id: 1, empresaId: 1, nome: 'Owner', email: 'owner@hub.com', role: 'owner', status: 'ativo', mustChangePassword: false };

const invoice = {
  id: 10, clientId: 1, consumerUnitId: 1, competencia: '2026-01',
  statusExtracao: 'extraida', statusValidacao: 'valida', createdAt: '2026-01-01',
  clienteNome: 'Cliente Um', ucCodigo: 'UC-1', usinas: [{ id: 1, nome: 'Usina A' }],
  valorTotalConcessionaria: '150.00', dataVencimento: '2026-01-10',
  documentoDisponivel: false, temPendencia: false, gdIKwh: null, gdIIKwh: null, problemas: []
};
const problem = { code: 'UC_NOT_FOUND', message: 'UC 000111222333444 não está cadastrada em nenhum cliente.', fields: [] };
const paid = {
  id: 5, statusInterno: 'emitida', asaasStatus: 'received', asaasId: 'pay_1', valor: 90, mesVencimento: '2026-01-20',
  boletoUrl: 'https://asaas.test/b/1', invoiceUrl: 'https://asaas.test/i/1', billingMode: 'separate'
};

function stubInvoicePage(data: Array<Record<string, unknown>> = [invoice]) {
  vi.mocked(getBillingInvoicePage).mockResolvedValue({ data: data as never, pagination: { page: 1, pageSize: 25, total: data.length, pages: 1 } });
}

function button(root: ParentNode, text: string): HTMLButtonElement | undefined {
  return Array.from(root.querySelectorAll('button')).find((item) => item.textContent === text);
}

describe('FaturasPage', () => {
  beforeEach(() => {
    window.dispatchEvent(new PopStateEvent('popstate')); // pages from earlier tests "leave"
    vi.clearAllMocks();
    document.body.replaceChildren();
    window.history.replaceState({}, '', '/');
    vi.mocked(getCurrentUser).mockReturnValue(owner as never);
    vi.mocked(getFaturas).mockResolvedValue([]);
    vi.mocked(getPendencias).mockResolvedValue([]);
    vi.mocked(getClients).mockResolvedValue([]);
    vi.mocked(getUcs).mockResolvedValue([]);
  });
  afterEach(() => { vi.restoreAllMocks(); });

  it('renders one row per invoice with the columns in order', async () => {
    stubInvoicePage([invoice, { ...invoice, id: 11, clienteNome: 'Cliente Dois' }]);
    const content = createFaturasPage();
    await flush();
    expect(getBillingInvoicePage).toHaveBeenCalledTimes(1);
    expect(content.querySelectorAll('tbody tr')).toHaveLength(2);
    expect(Array.from(content.querySelectorAll('th')).map((th) => th.textContent)).toEqual(
      ['Competência', 'Cliente / UC', 'Usina', 'Extração', 'GD I', 'GD II', 'Valor Copel', 'Boleto', 'Ações']);
    expect(content.textContent).toContain('Cliente Um');
    expect(content.textContent).toContain('UC-1');
    expect(content.textContent).toContain('Extraída');
    expect(content.textContent).toContain('Sem boleto');
  });

  it('shows the extraction problem text and Reprocessar for an invoice with problems', async () => {
    stubInvoicePage([{ ...invoice, problemas: [problem] }]);
    const content = createFaturasPage();
    await flush();
    expect(content.textContent).toContain('Erro');
    expect(content.textContent).toContain(problem.message);
    expect(button(content, 'Reprocessar')).toBeDefined();
    expect(button(content, 'Deletar')).toBeDefined();
  });

  it('paid boleto shows Pago, Boleto and Link and no Deletar', async () => {
    stubInvoicePage([{ ...invoice, contextualCharges: [paid] }]);
    const content = createFaturasPage();
    await flush();
    expect(content.textContent).toContain('Pago');
    const boleto = Array.from(content.querySelectorAll('a')).find((a) => a.textContent === 'Boleto');
    expect(boleto?.getAttribute('href')).toBe('https://asaas.test/b/1');
    expect(boleto?.getAttribute('rel')).toBe('noopener noreferrer');
    expect(boleto?.getAttribute('target')).toBe('_blank');
    expect(button(content, 'Link')).toBeDefined();
    expect(button(content, 'Deletar')).toBeUndefined();
    expect(button(content, 'Reprocessar')).toBeUndefined();
  });

  it('only opens boleto urls starting with https://', async () => {
    stubInvoicePage([{ ...invoice, contextualCharges: [{ ...paid, boletoUrl: 'javascript:alert(1)', invoiceUrl: null }] }]);
    const content = createFaturasPage();
    await flush();
    expect(Array.from(content.querySelectorAll('a')).some((a) => a.textContent === 'Boleto')).toBe(false);
  });

  it('pending and overdue charges show Aguardando pagamento and Vencido', async () => {
    stubInvoicePage([
      { ...invoice, contextualCharges: [{ ...paid, asaasStatus: 'pending' }] },
      { ...invoice, id: 11, contextualCharges: [{ ...paid, id: 6, asaasStatus: 'overdue' }] },
    ]);
    const content = createFaturasPage();
    await flush();
    expect(content.textContent).toContain('Aguardando pagamento');
    expect(content.textContent).toContain('Vencido');
  });

  it('charge without asaasId is not a boleto yet: no Boleto, Link, Deletar or Reprocessar', async () => {
    stubInvoicePage([{ ...invoice, problemas: [problem], contextualCharges: [{ ...paid, asaasId: null, asaasStatus: 'pending', boletoUrl: null, invoiceUrl: null }] }]);
    const content = createFaturasPage();
    await flush();
    expect(content.textContent).toContain('Sem boleto');
    expect(button(content, 'Link')).toBeUndefined();
    expect(button(content, 'Deletar')).toBeUndefined();
    expect(button(content, 'Reprocessar')).toBeUndefined();
  });

  it('ignores canceled charges', async () => {
    stubInvoicePage([{ ...invoice, contextualCharges: [{ ...paid, asaasStatus: 'canceled' }] }]);
    const content = createFaturasPage();
    await flush();
    expect(content.textContent).toContain('Sem boleto');
    expect(button(content, 'Deletar')).toBeDefined();
  });

  it('formats GD kWh and the dash', async () => {
    stubInvoicePage([{ ...invoice, gdIKwh: '30', gdIIKwh: null }]);
    const content = createFaturasPage();
    await flush();
    const cells = Array.from(content.querySelectorAll('tbody tr td')).map((td) => td.textContent);
    expect(cells[4]).toBe('30 kWh');
    expect(cells[5]).toBe('—');
  });

  it('Link copies the payment link and toasts', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
    stubInvoicePage([{ ...invoice, contextualCharges: [paid] }]);
    const content = createFaturasPage();
    await flush();
    button(content, 'Link')!.click();
    await flush();
    expect(writeText).toHaveBeenCalledWith('https://asaas.test/i/1');
    expect(toast.success).toHaveBeenCalledWith('Link de pagamento copiado.');
    expect(createFaturaInvoiceDetail).not.toHaveBeenCalled();
  });

  it('Link shows the url in an error toast when the clipboard rejects', async () => {
    Object.defineProperty(navigator, 'clipboard', { value: { writeText: vi.fn().mockRejectedValue(new Error('denied')) }, configurable: true });
    stubInvoicePage([{ ...invoice, contextualCharges: [paid] }]);
    const content = createFaturasPage();
    await flush();
    button(content, 'Link')!.click();
    await flush();
    expect(toast.error).toHaveBeenCalledWith(expect.stringContaining('https://asaas.test/i/1'));
  });

  it('Link does not copy a non-https url and toasts an error', async () => {
    const writeText = vi.fn();
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
    stubInvoicePage([{ ...invoice, contextualCharges: [{ ...paid, invoiceUrl: 'javascript:alert(1)', boletoUrl: 'http://x' }] }]);
    const content = createFaturasPage();
    await flush();
    button(content, 'Link')!.click();
    await flush();
    expect(writeText).not.toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalled();
  });

  it('platform admin outside the test empresa gets a read-only table: no Reprocessar or Deletar', async () => {
    vi.mocked(getCurrentUser).mockReturnValue({ id: 1, role: 'platform_admin', isPlatformAdmin: true, platformViewEmpresaId: 2 } as never);
    stubInvoicePage([{ ...invoice, problemas: [problem] }]);
    const content = createFaturasPage();
    await flush();
    expect(button(content, 'Reprocessar')).toBeUndefined();
    expect(button(content, 'Deletar')).toBeUndefined();
  });

  it('Deletar asks for confirmation, deletes, toasts and reloads', async () => {
    vi.mocked(deleteBillingInvoice).mockResolvedValue(undefined);
    stubInvoicePage();
    const content = createFaturasPage();
    await flush();
    button(content, 'Deletar')!.click();
    const dialog = document.body.querySelector('[role="dialog"]') as HTMLElement;
    expect(dialog.textContent).toContain('Cliente Um (01/2026)');
    expect(dialog.textContent).toContain('Importar o mesmo PDF de novo a restaura');
    expect(deleteBillingInvoice).not.toHaveBeenCalled();
    button(dialog, 'Deletar')!.click();
    await flush();
    expect(deleteBillingInvoice).toHaveBeenCalledWith(10, undefined);
    expect(toast.success).toHaveBeenCalledWith('Fatura excluída.');
    expect(getBillingInvoicePage).toHaveBeenCalledTimes(2);
    expect(document.body.querySelector('[role="dialog"]')).toBeNull();
  });

  it('Deletar shows the backend message on 409', async () => {
    vi.mocked(deleteBillingInvoice).mockRejectedValue(new ApiRequestError(409, 'Fatura com boleto ativo não pode ser excluída.', 'INVOICE_HAS_BOLETO'));
    stubInvoicePage();
    const content = createFaturasPage();
    await flush();
    button(content, 'Deletar')!.click();
    button(document.body.querySelector('[role="dialog"]') as HTMLElement, 'Deletar')!.click();
    await flush();
    expect(toast.error).toHaveBeenCalledWith('Fatura com boleto ativo não pode ser excluída.');
  });

  it('Reprocessar toasts success and reloads', async () => {
    vi.mocked(reprocessBillingInvoice).mockResolvedValue({ invoiceId: 10, duplicate: false, invoice: { problemas: [] } });
    stubInvoicePage([{ ...invoice, problemas: [problem] }]);
    const content = createFaturasPage();
    await flush();
    button(content, 'Reprocessar')!.click();
    await flush();
    expect(reprocessBillingInvoice).toHaveBeenCalledWith(10, undefined);
    expect(toast.success).toHaveBeenCalledWith('Fatura reprocessada e vinculada.');
    expect(getBillingInvoicePage).toHaveBeenCalledTimes(2);
  });

  it('Reprocessar that still has problems toasts the first problem message', async () => {
    vi.mocked(reprocessBillingInvoice).mockResolvedValue({ invoiceId: 10, duplicate: false, invoice: { problemas: [problem] } });
    stubInvoicePage([{ ...invoice, problemas: [problem] }]);
    const content = createFaturasPage();
    await flush();
    button(content, 'Reprocessar')!.click();
    await flush();
    expect(toast.error).toHaveBeenCalledWith(problem.message);
    expect(toast.success).not.toHaveBeenCalled();
  });

  it('Reprocessar shows the backend message on 409', async () => {
    vi.mocked(reprocessBillingInvoice).mockRejectedValue(new ApiRequestError(409, 'Reprocesso não permitido.', 'REPROCESS_NOT_ALLOWED'));
    stubInvoicePage([{ ...invoice, problemas: [problem] }]);
    const content = createFaturasPage();
    await flush();
    button(content, 'Reprocessar')!.click();
    await flush();
    expect(toast.error).toHaveBeenCalledWith('Reprocesso não permitido.');
  });

  it('shows the empty state when there are no invoices', async () => {
    stubInvoicePage([]);
    const content = createFaturasPage();
    await flush();
    expect(content.textContent).toContain('Nenhuma fatura encontrada');
  });

  it('shows an error state with retry when loading fails', async () => {
    vi.mocked(getBillingInvoicePage).mockRejectedValueOnce(new Error('network down'));
    const content = createFaturasPage();
    await flush();
    expect(content.textContent).toContain('Não foi possível carregar as faturas');
    stubInvoicePage();
    button(content, 'Tentar novamente')!.click();
    await flush();
    expect(content.textContent).toContain('Cliente Um');
  });

  it('reloads on the import event and stops listening once the page is left', async () => {
    stubInvoicePage();
    createFaturasPage();
    await flush();
    window.dispatchEvent(new Event('hub:invoices-imported'));
    await flush();
    expect(getBillingInvoicePage).toHaveBeenCalledTimes(2);
    window.dispatchEvent(new PopStateEvent('popstate'));
    window.dispatchEvent(new Event('hub:invoices-imported'));
    await flush();
    expect(getBillingInvoicePage).toHaveBeenCalledTimes(2);
  });

  it('does not render a second import button or a manual charge action', async () => {
    stubInvoicePage();
    const content = createFaturasPage();
    await flush();
    expect(content.textContent).not.toContain('Emitir cobrança');
    expect(content.textContent).not.toContain('Importar');
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

  it('platform admin na empresa de teste (id 1): carrega os dados tenant-scoped', async () => {
    vi.mocked(getCurrentUser).mockReturnValue({ id: 1, nome: 'Admin', role: 'platform_admin', isPlatformAdmin: true, platformViewEmpresaId: 1 } as never);
    createFaturasPage();
    await flush();
    expect(getFaturas).toHaveBeenCalledTimes(1);
    expect(getPendencias).toHaveBeenCalledTimes(1);
    expect(getClients).toHaveBeenCalledTimes(1);
    expect(getUcs).toHaveBeenCalledTimes(1);
  });

  it('platform admin fora da empresa de teste: nao carrega os dados tenant-scoped', async () => {
    vi.mocked(getCurrentUser).mockReturnValue({ id: 1, nome: 'Admin', role: 'platform_admin', isPlatformAdmin: true, platformViewEmpresaId: 2 } as never);
    createFaturasPage();
    await flush();
    expect(getFaturas).not.toHaveBeenCalled();
    expect(getPendencias).not.toHaveBeenCalled();
    expect(getClients).not.toHaveBeenCalled();
    expect(getUcs).not.toHaveBeenCalled();
  });
});
