import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../services/apiClient', () => ({
  apiRequest: vi.fn(),
  apiUpload: vi.fn(),
  apiBlobWithHeaders: vi.fn(),
}));

import { apiRequest } from '../services/apiClient';
import { calculateBillingInvoice, reprocessBillingInvoice } from '../services/billingCalculationsService';

describe('billingCalculationsService', () => {
  beforeEach(() => {
    vi.mocked(apiRequest).mockReset();
  });

  it('reprocessa fatura pelo path do tenant', async () => {
    const upload = { invoiceId: 7, duplicate: false, invoice: {} };
    vi.mocked(apiRequest).mockResolvedValue({ data: upload });

    expect(await reprocessBillingInvoice(7)).toEqual(upload);
    expect(apiRequest).toHaveBeenCalledWith('/billing-calculations/invoices/7/reprocess', { method: 'POST' });
  });

  it('reprocessa fatura pelo path da plataforma com empresaId', async () => {
    vi.mocked(apiRequest).mockResolvedValue({ data: { invoiceId: 7 } });

    await reprocessBillingInvoice(7, 3);

    expect(apiRequest).toHaveBeenCalledWith('/platform/empresas/3/billing-calculations/invoices/7/reprocess', { method: 'POST' });
  });

  it('calcula fatura pelo path do tenant quando empresaId e indefinido', async () => {
    const execution = { id: 1, invoiceId: 7, status: 'CALCULATED' };
    vi.mocked(apiRequest).mockResolvedValue({ data: execution });

    expect(await calculateBillingInvoice(7)).toEqual(execution);
    expect(apiRequest).toHaveBeenCalledWith('/billing-calculations/invoices/7/execute', { method: 'POST' });
  });

  it('calcula fatura pelo path da plataforma com empresaId', async () => {
    vi.mocked(apiRequest).mockResolvedValue({ data: { id: 1 } });

    await calculateBillingInvoice(7, 3);

    expect(apiRequest).toHaveBeenCalledWith('/platform/empresas/3/billing-calculations/invoices/7/execute', { method: 'POST' });
  });

  it('propaga erro da API', async () => {
    vi.mocked(apiRequest).mockRejectedValue(new Error('boom'));

    await expect(reprocessBillingInvoice(7)).rejects.toThrow('boom');
    await expect(calculateBillingInvoice(7)).rejects.toThrow('boom');
  });
});
