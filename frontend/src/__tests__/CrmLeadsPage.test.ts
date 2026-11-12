import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../layouts/BaseLayout', () => ({
  createBaseLayout: ({ content }: { content: HTMLElement }) => content,
}));

vi.mock('../services/crmLeadService', () => ({
  getCrmLeads: vi.fn(),
  sincronizarCrmLeads: vi.fn(),
}));

import { getCrmLeads, sincronizarCrmLeads } from '../services/crmLeadService';
import { createCrmLeadsPage } from '../pages/CrmLeadsPage';

async function flush(): Promise<void> {
  await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
}

const lead = {
  id: 1, provider: 'piperun', externalId: '10', titulo: 'Negócio Solar X', status: 0, valor: '1500.00',
  pipelineNome: 'Vendas', etapaNome: 'Proposta', criadoEmOrigem: null, atualizadoEmOrigem: null,
  importadoEm: '2026-01-01T00:00:00', atualizadoEm: '2026-01-01T00:00:00'
};

describe('CrmLeadsPage', () => {
  beforeEach(() => { vi.clearAllMocks(); });
  afterEach(() => { vi.restoreAllMocks(); });

  it('renders one row per imported lead', async () => {
    vi.mocked(getCrmLeads).mockResolvedValue([lead]);
    const content = createCrmLeadsPage();
    await flush();
    expect(content.textContent).toContain('Negócio Solar X');
  });

  it('shows the empty state when there are no leads yet', async () => {
    vi.mocked(getCrmLeads).mockResolvedValue([]);
    const content = createCrmLeadsPage();
    await flush();
    expect(content.textContent).toContain('Nenhum lead importado ainda');
  });

  it('calls sincronizarCrmLeads and reloads the list when the sync button is clicked', async () => {
    vi.mocked(getCrmLeads).mockResolvedValue([]);
    vi.mocked(sincronizarCrmLeads).mockResolvedValue({ totalImportados: 2, totalAtualizados: 1 });
    const content = createCrmLeadsPage();
    await flush();

    const syncButton = Array.from(content.querySelectorAll('button')).find((button) => button.textContent?.includes('Sincronizar agora'));
    expect(syncButton).toBeInstanceOf(HTMLButtonElement);
    vi.mocked(getCrmLeads).mockResolvedValue([lead]);
    syncButton?.click();
    await flush();

    expect(sincronizarCrmLeads).toHaveBeenCalledTimes(1);
    expect(getCrmLeads).toHaveBeenCalledTimes(2);
    expect(content.textContent).toContain('Negócio Solar X');
  });
});
