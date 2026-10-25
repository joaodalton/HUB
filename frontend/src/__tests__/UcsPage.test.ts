import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../layouts/BaseLayout', () => ({
  createBaseLayout: ({ content }: { content: HTMLElement }) => content,
}));

vi.mock('../services/plantService', () => ({
  getAvailablePlants: vi.fn(),
}));

vi.mock('../services/clientsService', () => ({
  getClients: vi.fn(),
}));

vi.mock('../services/billingRulesService', () => ({
  listBillingRules: vi.fn(),
  listBillingRuleAssignments: vi.fn(),
}));

vi.mock('../services/ucsService', async () => {
  const actual = await vi.importActual<typeof import('../services/ucsService')>('../services/ucsService');
  return {
    ...actual,
    getUcs: vi.fn(),
    createUc: vi.fn(),
    updateUc: vi.fn(),
    deleteUc: vi.fn(),
  };
});

import { getUcs } from '../services/ucsService';
import { getClients } from '../services/clientsService';
import { getAvailablePlants } from '../services/plantService';
import { listBillingRules, listBillingRuleAssignments } from '../services/billingRulesService';
import { createUcsPage } from '../pages/UcsPage';

async function flush(): Promise<void> {
  await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
}

const uc = {
  id: 1, clienteId: 1, clienteNome: 'Fulano', codigo: 'UC-1', apelido: '', documento: null,
  endereco: null, cep: null, concessionaria: 'Copel', geracaoPropria: false, diaEmissaoFatura: null,
  consumo: 100, baseTarifaria: 'B1', desconto: '10%', tipoLigacao: 'Monofasico' as const,
  inicioContrato: null, terminoContrato: null, carenciaMeses: null, percentualDescontoCarencia: null,
  conexoes: []
};

describe('UcsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.history.replaceState({}, '', '/');
    vi.mocked(getClients).mockResolvedValue([]);
    vi.mocked(getAvailablePlants).mockResolvedValue([]);
    vi.mocked(listBillingRules).mockResolvedValue([]);
    vi.mocked(listBillingRuleAssignments).mockResolvedValue([]);
  });
  afterEach(() => { vi.restoreAllMocks(); });

  it('renders one row per UC when ready', async () => {
    vi.mocked(getUcs).mockResolvedValue([uc]);
    const content = createUcsPage();
    await flush();
    expect(getUcs).toHaveBeenCalledTimes(1);
    expect(content.textContent).toContain('UC-1');
    expect(content.textContent).toContain('Fulano');
  });

  it('shows the empty state when there are no UCs', async () => {
    vi.mocked(getUcs).mockResolvedValue([]);
    const content = createUcsPage();
    await flush();
    expect(content.textContent).toContain('Nenhuma UC cadastrada');
  });

  it('shows an error state when loading fails', async () => {
    vi.mocked(getUcs).mockRejectedValue(new Error('offline'));
    const content = createUcsPage();
    await flush();
    expect(content.textContent).toContain('Nao foi possivel carregar UCs');
  });

  it('filters by the "without plant" quick filter', async () => {
    const withPlant = { ...uc, id: 2, codigo: 'UC-2', conexoes: [{ id: 1, plantId: 1, usina: 'Usina A', percentual: '100' }] };
    vi.mocked(getUcs).mockResolvedValue([uc, withPlant]);
    const content = createUcsPage();
    await flush();

    const button = Array.from(content.querySelectorAll('button')).find((item) => item.textContent === 'Sem usina');
    expect(button).toBeInstanceOf(HTMLButtonElement);
    button?.click();

    expect(content.textContent).toContain('UC-1');
    expect(content.textContent).not.toContain('UC-2');
  });

  it('opens the UC detail panel when a row is clicked', async () => {
    vi.mocked(getUcs).mockResolvedValue([uc]);
    const content = createUcsPage();
    await flush();
    const row = content.querySelector('tbody tr');
    expect(row).not.toBeNull();
    row?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flush();
    expect(content.querySelector('.detail-info-panel')).not.toBeNull();
  });
});
