import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../layouts/PlatformLayout', () => ({
  createPlatformLayout: ({ content }: { content: HTMLElement }) => content,
}));

vi.mock('../services/platformWorkerService', async () => {
  const actual = await vi.importActual<typeof import('../services/platformWorkerService')>('../services/platformWorkerService');
  return {
    ...actual,
    getPlatformWorkers: vi.fn(),
    createPlatformWorker: vi.fn(),
    revokePlatformWorker: vi.fn(),
  };
});

import { getPlatformWorkers, createPlatformWorker } from '../services/platformWorkerService';
import { createPlatformFuncionariosPage } from '../pages/PlatformFuncionariosPage';

async function flush(): Promise<void> {
  await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
}

const worker = {
  id: 1,
  nome: 'Fiscal Um',
  email: 'fiscal@hub.com',
  role: 'viewer',
  status: 'ativo',
  isPlatformAdmin: false,
  isPlatformWorker: true,
};

describe('PlatformFuncionariosPage', () => {
  beforeEach(() => { vi.clearAllMocks(); });
  afterEach(() => { vi.restoreAllMocks(); });

  it('renders one row per platform worker', async () => {
    vi.mocked(getPlatformWorkers).mockResolvedValue([worker]);
    const content = createPlatformFuncionariosPage();
    await flush();
    expect(getPlatformWorkers).toHaveBeenCalledTimes(1);
    expect(content.textContent).toContain('fiscal@hub.com');
  });

  it('calls createPlatformWorker with the form values on submit', async () => {
    vi.mocked(getPlatformWorkers).mockResolvedValue([]);
    vi.mocked(createPlatformWorker).mockResolvedValue(worker);
    const content = createPlatformFuncionariosPage();
    document.body.appendChild(content);
    await flush();

    const openButton = Array.from(content.querySelectorAll('button')).find((button) => button.textContent?.includes('Novo fiscal'));
    expect(openButton).toBeInstanceOf(HTMLButtonElement);
    openButton?.click();

    const nomeInput = content.querySelector<HTMLInputElement>('input[name="nome"]');
    const emailInput = content.querySelector<HTMLInputElement>('input[name="email"]');
    const senhaInput = content.querySelector<HTMLInputElement>('input[name="senha"]');
    expect(nomeInput).toBeInstanceOf(HTMLInputElement);
    expect(emailInput).toBeInstanceOf(HTMLInputElement);
    expect(senhaInput).toBeInstanceOf(HTMLInputElement);

    nomeInput!.value = 'Novo Fiscal';
    nomeInput!.dispatchEvent(new Event('input'));
    emailInput!.value = 'novo@hub.com';
    emailInput!.dispatchEvent(new Event('input'));
    senhaInput!.value = 'senha123';
    senhaInput!.dispatchEvent(new Event('input'));

    const submitButton = Array.from(content.querySelectorAll('button')).find((button) => button.textContent?.includes('Criar'));
    expect(submitButton).toBeInstanceOf(HTMLButtonElement);
    submitButton?.click();
    await flush();

    expect(createPlatformWorker).toHaveBeenCalledWith({ nome: 'Novo Fiscal', email: 'novo@hub.com', senha: 'senha123' });
  });
});
