import { describe, it, expect, vi, beforeEach } from 'vitest';
import { createReportsPage } from '../pages/ReportsPage';
import * as reportsService from '../services/reportsService';
import * as googleAccountService from '../services/googleAccountService';
import { ApiRequestError } from '../services/apiClient';

vi.mock('../layouts/BaseLayout', () => ({
  createBaseLayout: ({ content }: { content: HTMLElement }) => content,
}));

// Painéis de template agora ficam dentro do modal "Templates" (anexado em
// document.body, fora de `page`) -- abre o modal antes de interagir com eles.
async function openTemplatesModal(page: HTMLElement): Promise<void> {
  const button = Array.from(page.querySelectorAll('button')).find((b) => b.textContent?.includes('Templates')) as HTMLButtonElement;
  button.click();
  await new Promise((resolve) => setTimeout(resolve, 0));
}

describe('ReportsPage', () => {
  beforeEach(() => {
    vi.spyOn(reportsService, 'getReportTypes').mockResolvedValue([{ tipo: 'cadastro', label: 'Cadastro' }]);
    vi.spyOn(reportsService, 'getReportTemplates').mockResolvedValue([{ id: 'padrao', label: 'Padrão (sem cor)', editable: false }]);
    vi.spyOn(reportsService, 'getSourceTemplate').mockResolvedValue({ tipoOrigem: null, driveFileId: null, documentoNome: null });
  });

  it('mostra o link do Google apos gerar com sucesso', async () => {
    vi.spyOn(reportsService, 'generateReport').mockResolvedValue({ driveFileId: 'x', webViewLink: 'https://drive.google.com/x' });
    const page = createReportsPage();
    document.body.appendChild(page);
    await new Promise((resolve) => setTimeout(resolve, 0));
    const button = page.querySelector('.report-card button') as HTMLButtonElement;
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
    const button = page.querySelector('.report-card button') as HTMLButtonElement;
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
    const button = page.querySelector('.report-card button') as HTMLButtonElement;
    button.click();
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(generateReportSpy).toHaveBeenCalledWith('financeiro', 'doc', '2026-09', 'padrao');
  });

  it('cria um template proprio com nome e cor sem # e recarrega a lista', async () => {
    const createSpy = vi.spyOn(reportsService, 'createReportTemplate').mockResolvedValue({ id: 'custom:1', label: 'Minha marca', editable: true, accentHex: '2563EB' });
    const page = createReportsPage();
    document.body.appendChild(page);
    await new Promise((resolve) => setTimeout(resolve, 0));
    await openTemplatesModal(page);

    const nomeInput = document.querySelector('input[type="text"]') as HTMLInputElement;
    const corInput = document.querySelector('input[type="color"]') as HTMLInputElement;
    nomeInput.value = '  Minha marca  ';
    corInput.value = '#2563eb';
    const form = nomeInput.closest('form') as HTMLFormElement;
    form.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(createSpy).toHaveBeenCalledWith('Minha marca', '2563EB');
  });

  it('extrai o fileId de um link colado do Google Doc ao configurar a origem', async () => {
    const setDriveSpy = vi.spyOn(reportsService, 'setSourceTemplateDrive').mockResolvedValue({ tipoOrigem: 'drive', driveFileId: 'ABC123', documentoNome: null });
    const page = createReportsPage();
    document.body.appendChild(page);
    await new Promise((resolve) => setTimeout(resolve, 0));
    await openTemplatesModal(page);

    const driveInput = Array.from(document.querySelectorAll('input[type="text"]'))
      .find((el) => (el as HTMLInputElement).placeholder.includes('Google Doc')) as HTMLInputElement;
    driveInput.value = 'https://docs.google.com/document/d/ABC123/edit?usp=drivesdk';
    const form = driveInput.closest('form') as HTMLFormElement;
    form.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(setDriveSpy).toHaveBeenCalledWith('documento', 'ABC123');
  });

  it('mostra o template de documento configurado e permite remover', async () => {
    vi.spyOn(reportsService, 'getSourceTemplate').mockResolvedValue({ tipoOrigem: 'upload', driveFileId: null, documentoNome: 'modelo-empresa.docx' });
    const removeSpy = vi.spyOn(reportsService, 'removeSourceTemplate').mockResolvedValue(undefined);
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    const page = createReportsPage();
    document.body.appendChild(page);
    await new Promise((resolve) => setTimeout(resolve, 0));
    await openTemplatesModal(page);

    expect(document.body.textContent).toContain('modelo-empresa.docx');
    const removeButton = Array.from(document.querySelectorAll('button')).find((b) => b.textContent?.includes('Remover')) as HTMLButtonElement;
    removeButton.click();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(removeSpy).toHaveBeenCalled();
  });

  it('mostra os 3 paineis de template de origem (documento/planilha/apresentacao) dentro do modal', async () => {
    const page = createReportsPage();
    document.body.appendChild(page);
    await new Promise((resolve) => setTimeout(resolve, 0));
    await openTemplatesModal(page);

    expect(document.body.textContent).toContain('Documento');
    expect(document.body.textContent).toContain('Planilha');
    expect(document.body.textContent).toContain('Apresentação');
  });
});
