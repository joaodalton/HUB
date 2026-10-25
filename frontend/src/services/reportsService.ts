import { apiBlobWithHeaders, apiRequest, type ApiResponse } from './apiClient';

export type ReportType = 'cadastro' | 'financeiro' | 'rateio';
export type ReportFormat = 'doc' | 'sheet' | 'slide' | 'docx' | 'xlsx' | 'pptx';
export type ReportTypeOption = { tipo: ReportType; label: string };
export type GeneratedReport = { driveFileId: string; webViewLink: string };

export async function getReportTypes(): Promise<ReportTypeOption[]> {
  return (await apiRequest<ApiResponse<ReportTypeOption[]>>('/reports/tipos')).data;
}

export async function generateReport(tipo: ReportType, formato: ReportFormat, competencia?: string): Promise<GeneratedReport> {
  return (await apiRequest<ApiResponse<GeneratedReport>>('/reports/gerar', {
    method: 'POST',
    body: { tipo, formato, ...(competencia ? { competencia } : {}) },
  })).data;
}

// Formatos office (docx/xlsx/pptx) sao gerados localmente e devolvidos como
// binario -- mesmo padrao de downloadDocumentFile em documentsService.ts.
function filenameFromContentDisposition(contentDisposition: string | null, fallback: string): string {
  const match = contentDisposition?.match(/filename="?([^"]+)"?/);
  return match ? match[1] : fallback;
}

export async function downloadReportFile(tipo: ReportType, formato: ReportFormat, competencia?: string): Promise<void> {
  const { blob, contentDisposition } = await apiBlobWithHeaders('/reports/gerar', {
    method: 'POST',
    body: { tipo, formato, ...(competencia ? { competencia } : {}) },
  });
  const filename = filenameFromContentDisposition(contentDisposition, `relatorio.${formato}`);
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');

  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
