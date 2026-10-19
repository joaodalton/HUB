import { describe, it, expect, vi, beforeEach } from 'vitest';
import { createReportsPage } from '../pages/ReportsPage';
import * as reportsService from '../services/reportsService';
import * as googleAccountService from '../services/googleAccountService';
import { ApiRequestError } from '../services/apiClient';

vi.mock('../layouts/BaseLayout', () => ({
  createBaseLayout: ({ content }: { content: HTMLElement }) => content,
}));

describe('ReportsPage', () => {
  beforeEach(() => {
    vi.spyOn(reportsService, 'getReportTypes').mockResolvedValue([{ tipo: 'cadastro', label: 'Cadastro' }]);
  });

  it('mostra o link do Google apos gerar com sucesso', async () => {
    vi.spyOn(reportsService, 'generateReport').mockResolvedValue({ driveFileId: 'x', webViewLink: 'https://drive.google.com/x' });
    const page = createReportsPage();
    document.body.appendChild(page);
    await new Promise((resolve) => setTimeout(resolve, 0));
    const button = page.querySelector('button') as HTMLButtonElement;
    button.click();
    await new Promise((resolve) => setTimeout(resolve, 0));
    const link = page.querySelector('a[href="https://drive.google.com/x"]');
    expect(link).not.toBeNull();
  });

  it('mostra aviso de reconectar quando a API retorna GOOGLE_SCOPE_MISSING', async () => {
    vi.spyOn(reportsService, 'generateReport').mockRejectedValue(new ApiRequestError(409, 'sem escopo', 'GOOGLE_SCOPE_MISSING'));
    vi.spyOn(googleAccountService, 'getGoogleAuthorizeUrl').mockReturnValue('https://accounts.google.com/x');
    const page = createReportsPage();
    document.body.appendChild(page);
    await new Promise((resolve) => setTimeout(resolve, 0));
    const button = page.querySelector('button') as HTMLButtonElement;
    button.click();
    await new Promise((resolve) => setTimeout(resolve, 0));
    const reconnect = page.querySelector('a[href="https://accounts.google.com/x"]');
    expect(reconnect).not.toBeNull();
  });

  it('envia a competencia preenchida ao gerar relatorio financeiro', async () => {
    vi.spyOn(reportsService, 'getReportTypes').mockResolvedValue([{ tipo: 'financeiro', label: 'Financeiro' }]);
    const generateReportSpy = vi.spyOn(reportsService, 'generateReport').mockResolvedValue({ driveFileId: 'x', webViewLink: 'https://drive.google.com/x' });
    const page = createReportsPage();
    document.body.appendChild(page);
    await new Promise((resolve) => setTimeout(resolve, 0));
    const competenciaInput = page.querySelector('input[type="month"]') as HTMLInputElement;
    competenciaInput.value = '2026-09';
    const button = page.querySelector('button') as HTMLButtonElement;
    button.click();
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(generateReportSpy).toHaveBeenCalledWith('financeiro', 'doc', '2026-09');
  });
});
