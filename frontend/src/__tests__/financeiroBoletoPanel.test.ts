import { beforeEach, describe, expect, it, vi } from 'vitest';

const toast = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() }));
vi.mock('../hooks/useToast', () => ({ useToast: () => toast }));
vi.mock('../services/billingCalculationsService', () => ({ downloadBillingInvoice: vi.fn() }));

import { downloadBillingInvoice } from '../services/billingCalculationsService';
import { openBoletoPanel } from '../pages/financeiroBoletoPanel';

const fatura = (over: Record<string, unknown> = {}) => ({
  id: 1, billingMode: 'unified', boletoUrl: 'https://asaas.test/b/1', invoiceUrl: 'https://asaas.test/i/1', ...over
}) as never;

const labels = () => Array.from(document.querySelectorAll('.hub-modal button, .hub-modal a')).map((el) => el.textContent);
const byText = (text: string) => Array.from(document.querySelectorAll('button')).find((b) => b.textContent === text) as HTMLButtonElement;

describe('openBoletoPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    document.body.replaceChildren();
  });

  it('shows 3 actions for unified', () => {
    openBoletoPanel(fatura(), { invoiceId: 10, onClose: vi.fn() });
    expect(document.querySelector('h2')?.textContent).toBe('Boleto gerado');
    expect(labels()).toEqual(expect.arrayContaining(['Baixar boleto', 'Copiar link de pagamento', 'Fatura Copel (PDF)']));
  });

  it.each(['separate', null])('hides the utility PDF for %s', (mode) => {
    openBoletoPanel(fatura({ billingMode: mode }), { invoiceId: 10, onClose: vi.fn() });
    expect(labels()).toContain('Baixar boleto');
    expect(labels()).not.toContain('Fatura Copel (PDF)');
  });

  it('downloads the utility PDF with the invoice id', () => {
    vi.mocked(downloadBillingInvoice).mockResolvedValue(undefined);
    openBoletoPanel(fatura(), { invoiceId: 10, empresaId: 3, onClose: vi.fn() });
    byText('Fatura Copel (PDF)').click();
    expect(downloadBillingInvoice).toHaveBeenCalledWith(10, 3);
  });

  it('copies invoiceUrl, falling back to boletoUrl', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    openBoletoPanel(fatura({ invoiceUrl: null }), { invoiceId: 10, onClose: vi.fn() });
    byText('Copiar link de pagamento').click();
    await Promise.resolve();
    expect(writeText).toHaveBeenCalledWith('https://asaas.test/b/1');
  });

  it('refuses to copy or open non-https urls', async () => {
    const writeText = vi.fn();
    Object.assign(navigator, { clipboard: { writeText } });
    openBoletoPanel(fatura({ invoiceUrl: 'javascript:alert(1)', boletoUrl: 'http://x' }), { invoiceId: 10, onClose: vi.fn() });
    expect(document.querySelector('.hub-modal a')).toBeNull();
    byText('Copiar link de pagamento').click();
    await Promise.resolve();
    expect(writeText).not.toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalled();
  });

  it('opens the boleto safely and calls onClose when closed', () => {
    const onClose = vi.fn();
    openBoletoPanel(fatura(), { invoiceId: 10, onClose });
    const link = document.querySelector('.hub-modal a') as HTMLAnchorElement;
    expect(link.href).toBe('https://asaas.test/b/1');
    expect(link.target).toBe('_blank');
    expect(link.rel).toBe('noopener noreferrer');
    byText('Fechar').click();
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
