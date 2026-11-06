import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../services/apiClient', () => ({
  apiRequest: vi.fn(),
}));

import { apiRequest } from '../services/apiClient';
import { getFinanceiroDashboard, type FinanceiroDashboard } from '../services/financeiroService';

const dashboard: FinanceiroDashboard = {
  porCliente: [{ clienteId: 1, clienteNome: 'Cliente A', recebido: '100.00', pendente: '25.50' }],
  porUsina: [
    { usinaId: 10, usinaNome: 'Usina X', recebido: '80.00', repasseCalculado: '60.00', contratoPendente: false },
    { usinaId: 11, usinaNome: 'Usina Y', recebido: '0.00', repasseCalculado: null, contratoPendente: true, semClientesConectados: true },
  ],
};

describe('financeiroService', () => {
  beforeEach(() => {
    vi.mocked(apiRequest).mockReset();
  });

  it('busca o dashboard financeiro com competencia opcional', async () => {
    vi.mocked(apiRequest).mockResolvedValue({ data: dashboard });

    const result = await getFinanceiroDashboard('2026-10');

    expect(apiRequest).toHaveBeenCalledWith('/financeiro/dashboard?competencia=2026-10');
    expect(result).toEqual(dashboard);
    expect(result.porCliente).toBeDefined();
    expect(result.porUsina).toBeDefined();
  });

  it('omite a query string quando a competencia nao e informada', async () => {
    vi.mocked(apiRequest).mockResolvedValue({ data: dashboard });

    await getFinanceiroDashboard();

    expect(apiRequest).toHaveBeenCalledWith('/financeiro/dashboard');
  });

  it('propaga erro da API', async () => {
    vi.mocked(apiRequest).mockRejectedValue(new Error('Falha na comunicacao com a API.'));

    await expect(getFinanceiroDashboard('2026-10')).rejects.toThrow('Falha na comunicacao com a API.');
  });
});
