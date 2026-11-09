import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../platform/layouts/PlatformLayout', () => ({
  createPlatformLayout: ({ content }: { content: HTMLElement }) => content,
}));

vi.mock('../platform/services/platformService', async () => {
  const actual = await vi.importActual<typeof import('../platform/services/platformService')>('../platform/services/platformService');
  return {
    ...actual,
    getPlatformOverview: vi.fn(),
    getPlatformEmpresas: vi.fn(),
  };
});

import { getPlatformEmpresas, getPlatformOverview } from '../platform/services/platformService';
import { calculateShare, createPlatformOverviewPage } from '../platform/pages/PlatformOverviewPage';

async function flush(): Promise<void> {
  await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
}

describe('calculateShare', () => {
  it('computes the percentage a value represents of a total', () => {
    expect(calculateShare(10, 50)).toBe(20);
  });

  it('returns 0 instead of NaN/Infinity when the total is zero', () => {
    expect(calculateShare(0, 0)).toBe(0);
    expect(calculateShare(5, 0)).toBe(0);
  });
});

describe('PlatformOverviewPage', () => {
  beforeEach(() => { vi.clearAllMocks(); });
  afterEach(() => { vi.restoreAllMocks(); });

  it('renders each company share of platform totals', async () => {
    vi.mocked(getPlatformOverview).mockResolvedValue({ totalEmpresas: 2, totalUsuarios: 15 });
    vi.mocked(getPlatformEmpresas).mockResolvedValue([
      { id: 1, nome: 'Empresa A', slug: 'a', status: 'ativo', cnpj: null, totalUsuarios: 10, totalClientes: 0, totalUcs: 10, totalUsinas: 2 },
      { id: 2, nome: 'Empresa B', slug: 'b', status: 'ativo', cnpj: null, totalUsuarios: 5, totalClientes: 0, totalUcs: 40, totalUsinas: 8 },
    ]);
    const content = createPlatformOverviewPage();
    await flush();

    expect(content.textContent).toContain('Empresa A');
    expect(content.textContent).toContain('20%');
    expect(content.textContent).toContain('66.7%');
  });

  it('shows an error state when the companies share fails to load', async () => {
    vi.mocked(getPlatformOverview).mockResolvedValue({ totalEmpresas: 0, totalUsuarios: 0 });
    vi.mocked(getPlatformEmpresas).mockRejectedValue(new Error('boom'));
    const content = createPlatformOverviewPage();
    await flush();
    expect(content.textContent).toContain('Não foi possível carregar a participação das empresas.');
  });
});
