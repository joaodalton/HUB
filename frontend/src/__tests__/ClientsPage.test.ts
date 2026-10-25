import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../layouts/BaseLayout', () => ({
  createBaseLayout: ({ content }: { content: HTMLElement }) => content,
}));

vi.mock('../services/plantService', () => ({
  getAvailablePlants: vi.fn(),
}));

vi.mock('../services/clientsService', async () => {
  const actual = await vi.importActual<typeof import('../services/clientsService')>('../services/clientsService');
  return {
    ...actual,
    getClients: vi.fn(),
    createClient: vi.fn(),
    updateClient: vi.fn(),
    deleteClient: vi.fn(),
  };
});

import { getClients } from '../services/clientsService';
import { getAvailablePlants } from '../services/plantService';
import { createClientsPage } from '../pages/ClientsPage';

async function flush(): Promise<void> {
  await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
}

const client = {
  id: 1, nome: 'Fulano da Silva', cpf: '000.000.000-00', email: 'fulano@hub.com',
  telefone: null, dataNascimento: null, uc: 'UC-1', usina: 'Usina A', consumo: '100',
  status: 'Concluido', concessionaria: 'Copel', ucs: []
};

describe('ClientsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.history.replaceState({}, '', '/');
    vi.mocked(getAvailablePlants).mockResolvedValue([]);
  });
  afterEach(() => { vi.restoreAllMocks(); });

  it('renders one row per client when ready', async () => {
    vi.mocked(getClients).mockResolvedValue([client]);
    const content = createClientsPage();
    await flush();
    expect(getClients).toHaveBeenCalledTimes(1);
    expect(content.textContent).toContain('Fulano da Silva');
  });

  it('shows the empty state when there are no clients', async () => {
    vi.mocked(getClients).mockResolvedValue([]);
    const content = createClientsPage();
    await flush();
    expect(content.textContent).toContain('Nenhum cliente cadastrado');
  });

  it('shows an error state when loading fails', async () => {
    vi.mocked(getClients).mockRejectedValue(new Error('offline'));
    const content = createClientsPage();
    await flush();
    expect(content.textContent).toContain('Nao foi possivel carregar clientes');
  });

  it('filters the table by search term', async () => {
    const other = { ...client, id: 2, nome: 'Outra Pessoa', uc: 'UC-2', usina: 'Usina B' };
    vi.mocked(getClients).mockResolvedValue([client, other]);
    const content = createClientsPage();
    await flush();
    document.body.appendChild(content);

    const search = content.querySelector<HTMLInputElement>('input[type="search"]');
    expect(search).toBeInstanceOf(HTMLInputElement);
    search!.value = 'Outra';
    search!.dispatchEvent(new Event('input'));
    await new Promise((resolve) => setTimeout(resolve, 350));
    await flush();

    expect(content.textContent).toContain('Outra Pessoa');
    expect(content.textContent).not.toContain('Fulano da Silva');
  });

  it('opens the client drawer when a row is clicked', async () => {
    vi.mocked(getClients).mockResolvedValue([client]);
    const content = createClientsPage();
    await flush();
    const row = content.querySelector('tbody tr');
    expect(row).not.toBeNull();
    row?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flush();
    expect(content.querySelector('.detail-drawer')).not.toBeNull();
  });
});
