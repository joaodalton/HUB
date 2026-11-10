import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../services/authService', () => ({ getCurrentUser: vi.fn() }));
vi.mock('../services/billingCalculationsService', () => ({
  uploadTenantBillingInvoice: vi.fn(),
  uploadBillingInvoice: vi.fn()
}));
const toast = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() }));
vi.mock('../hooks/useToast', () => ({ useToast: () => toast }));

import { ApiRequestError } from '../services/apiClient';
import { getCurrentUser } from '../services/authService';
import { uploadTenantBillingInvoice } from '../services/billingCalculationsService';
import { createInvoiceImportButton, INVOICES_IMPORTED_EVENT } from '../components/InvoiceImportButton';

const ucMessage = 'UC 000111222333444 não está cadastrada em nenhum cliente. Cadastre a UC e importe de novo.';
const upload = vi.mocked(uploadTenantBillingInvoice);
const okResult = (duplicate = false) => ({ invoiceId: 1, duplicate, invoice: {} as never });

function user(role: string) {
  vi.mocked(getCurrentUser).mockReturnValue({ role, isPlatformAdmin: false } as never);
}

async function pick(wrap: HTMLElement, names: string[]): Promise<void> {
  const input = wrap.querySelector('input') as HTMLInputElement;
  Object.defineProperty(input, 'files', { value: names.map((n) => new File(['x'], n, { type: 'application/pdf' })), configurable: true });
  input.dispatchEvent(new Event('change'));
  await vi.waitFor(() => expect(wrap.querySelector('button')!.disabled).toBe(false));
}

describe('createInvoiceImportButton', () => {
  const events: CustomEvent[] = [];
  beforeEach(() => {
    vi.clearAllMocks();
    document.body.replaceChildren();
    events.length = 0;
    window.addEventListener(INVOICES_IMPORTED_EVENT, ((e: Event) => events.push(e as CustomEvent)) as EventListener, { once: true });
    window.history.pushState({}, '', '/faturas');
  });

  it('retorna null sem usuario e para papel viewer', () => {
    vi.mocked(getCurrentUser).mockReturnValue(null);
    expect(createInvoiceImportButton()).toBeNull();
    user('viewer');
    expect(createInvoiceImportButton()).toBeNull();
  });

  it('aceita varios PDFs e mantem aria-label no input', () => {
    user('financial');
    const input = createInvoiceImportButton()!.querySelector('input')!;
    expect(input.multiple).toBe(true);
    expect(input.getAttribute('aria-label')).toBeTruthy();
  });

  it('envia em sequencia, lista cada arquivo no modal com a mensagem literal e dispara o evento', async () => {
    user('owner');
    upload.mockResolvedValueOnce(okResult()).mockRejectedValueOnce(new Error(ucMessage)).mockResolvedValueOnce(okResult());
    const wrap = createInvoiceImportButton()!;
    await pick(wrap, ['a.pdf', 'b.pdf', 'c.pdf']);
    expect(upload).toHaveBeenCalledTimes(3);
    const rows = document.querySelectorAll('.hub-modal li');
    expect(rows).toHaveLength(3);
    expect(document.querySelector('.hub-modal')!.textContent).toContain(ucMessage);
    expect(rows[1].textContent).toContain('b.pdf');
    expect(events[0].detail).toEqual({ imported: 2, duplicates: 0, failed: 1 });
    expect(toast.success).toHaveBeenCalledWith('2 fatura(s) importada(s) e vinculada(s).', undefined);
  });

  it('duplicata conta em duplicatas, sem modal', async () => {
    user('owner');
    upload.mockResolvedValueOnce(okResult(true));
    await pick(createInvoiceImportButton()!, ['a.pdf']);
    expect(document.querySelector('.hub-modal')).toBeNull();
    expect(events[0].detail).toEqual({ imported: 0, duplicates: 1, failed: 0 });
    expect(toast.success.mock.calls[0][0]).toContain('1 já importada(s).');
  });

  it('nenhum sucesso nao dispara evento', async () => {
    user('owner');
    upload.mockRejectedValue(new Error(ucMessage));
    await pick(createInvoiceImportButton()!, ['a.pdf']);
    expect(events).toHaveLength(0);
    expect(toast.success).not.toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalledWith('Nenhuma fatura importada — 1 com erro.');
    expect(document.querySelector('.hub-modal')).not.toBeNull();
  });

  it('429 para o envio e marca os restantes como nao enviados', async () => {
    user('owner');
    upload.mockResolvedValueOnce(okResult()).mockRejectedValueOnce(new ApiRequestError(429, 'Too many requests'));
    await pick(createInvoiceImportButton()!, ['a.pdf', 'b.pdf', 'c.pdf']);
    expect(upload).toHaveBeenCalledTimes(2);
    const rows = Array.from(document.querySelectorAll('.hub-modal li')).map((li) => li.textContent);
    expect(rows[1]).toContain('limite de envios por minuto');
    expect(rows[2]).toContain('limite de envios por minuto');
  });

  it('fora de /faturas oferece Ver em Faturas', async () => {
    user('owner');
    window.history.pushState({}, '', '/clientes');
    upload.mockResolvedValueOnce(okResult()).mockRejectedValueOnce(new Error(ucMessage));
    await pick(createInvoiceImportButton()!, ['a.pdf', 'b.pdf']);
    expect(toast.success.mock.calls[0][1]).toMatchObject({ label: 'Ver em Faturas' });
    const link = Array.from(document.querySelectorAll('.hub-modal button')).find((b) => b.textContent === 'Ver em Faturas') as HTMLButtonElement;
    link.click();
    expect(window.location.pathname).toBe('/faturas');
  });
});
