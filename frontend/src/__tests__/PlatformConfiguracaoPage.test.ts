import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../platform/layouts/PlatformLayout', () => ({
  createPlatformLayout: ({ content }: { content: HTMLElement }) => content,
}));

vi.mock('../platform/services/platformConfigService', async () => {
  const actual = await vi.importActual<typeof import('../platform/services/platformConfigService')>('../platform/services/platformConfigService');
  return {
    ...actual,
    getPlatformConfiguracao: vi.fn(),
    updatePlatformConfiguracao: vi.fn(),
  };
});

import { getPlatformConfiguracao, updatePlatformConfiguracao } from '../platform/services/platformConfigService';
import { createPlatformConfiguracaoPage } from '../platform/pages/PlatformConfiguracaoPage';

async function flush(): Promise<void> {
  await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
}

const config = {
  asaasApiBaseUrl: 'https://api-sandbox.asaas.com/v3',
  asaasApiKeyConfigurada: true,
  asaasWebhookTokenConfigurada: false,
  signupCodeConfigurada: false,
  signupEmpresaId: 7,
};

describe('PlatformConfiguracaoPage', () => {
  beforeEach(() => { vi.clearAllMocks(); });
  afterEach(() => { vi.restoreAllMocks(); });

  it('renders initial data loaded from GET', async () => {
    vi.mocked(getPlatformConfiguracao).mockResolvedValue(config);
    const content = createPlatformConfiguracaoPage();
    await flush();
    expect(getPlatformConfiguracao).toHaveBeenCalledTimes(1);
    const baseUrlInput = content.querySelector<HTMLInputElement>('input[type="text"]');
    expect(baseUrlInput?.value).toBe('https://api-sandbox.asaas.com/v3');
  });

  it('submits only the filled Asaas fields on save', async () => {
    vi.mocked(getPlatformConfiguracao).mockResolvedValue(config);
    vi.mocked(updatePlatformConfiguracao).mockResolvedValue(config);
    const content = createPlatformConfiguracaoPage();
    document.body.appendChild(content);
    await flush();

    const passwordInputs = Array.from(content.querySelectorAll<HTMLInputElement>('input[type="password"]'));
    const apiKeyInput = passwordInputs[0];
    apiKeyInput.value = 'new-key-value';
    apiKeyInput.dispatchEvent(new Event('input'));

    const saveButtons = Array.from(content.querySelectorAll('button')).filter((button) => button.textContent === 'Salvar');
    saveButtons[0]?.click();
    await flush();

    expect(updatePlatformConfiguracao).toHaveBeenCalledWith({ asaasApiKey: 'new-key-value' });
    document.body.removeChild(content);
  });

  it('shows an error toast when the API call fails', async () => {
    vi.mocked(getPlatformConfiguracao).mockRejectedValue(new Error('boom'));
    const content = createPlatformConfiguracaoPage();
    await flush();
    expect(content.textContent).toContain('Não foi possível carregar a configuração.');
  });
});
