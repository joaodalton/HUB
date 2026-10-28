import { apiBlobWithHeaders, apiRequest, apiUpload, type ApiResponse } from './apiClient';

export type ReportType = 'cadastro' | 'financeiro' | 'rateio' | 'producao';
export type ReportFormat = 'doc' | 'sheet' | 'slide' | 'docx' | 'xlsx' | 'pptx';
export type ReportTypeOption = { tipo: ReportType; label: string };
export type ReportTemplateOption = { id: string; label: string; editable: boolean; accentHex?: string | null };
export type GeneratedReport = { driveFileId: string; webViewLink: string };

export async function getReportTypes(): Promise<ReportTypeOption[]> {
  return (await apiRequest<ApiResponse<ReportTypeOption[]>>('/reports/tipos')).data;
}

export async function getReportTemplates(): Promise<ReportTemplateOption[]> {
  return (await apiRequest<ApiResponse<ReportTemplateOption[]>>('/reports/templates')).data;
}

export async function createReportTemplate(nome: string, accentHex: string | null): Promise<ReportTemplateOption> {
  return (await apiRequest<ApiResponse<ReportTemplateOption>>('/reports/templates', {
    method: 'POST',
    body: { nome, accentHex },
  })).data;
}

export async function updateReportTemplate(templateId: number, data: { nome?: string; accentHex?: string | null }): Promise<ReportTemplateOption> {
  return (await apiRequest<ApiResponse<ReportTemplateOption>>(`/reports/templates/${templateId}`, {
    method: 'PUT',
    body: data,
  })).data;
}

export async function deleteReportTemplate(templateId: number): Promise<void> {
  await apiRequest<ApiResponse<null>>(`/reports/templates/${templateId}`, { method: 'DELETE' });
}

// Template de ORIGEM, por categoria: em vez de gerar do zero, usa um
// arquivo que a empresa ja tem -- um arquivo do Google Drive dela (via
// Drive conectado) ou um arquivo office que ela sobe, com o marcador
// {{TABELA}} no lugar onde a tabela de dados entra.
// documento -> doc/docx, planilha -> sheet/xlsx, apresentacao -> slide/pptx.
export type SourceTemplateCategory = 'documento' | 'planilha' | 'apresentacao';

export type SourceTemplateConfig = {
  tipoOrigem: 'drive' | 'upload' | null;
  driveFileId: string | null;
  documentoNome: string | null;
};

export async function getSourceTemplate(categoria: SourceTemplateCategory): Promise<SourceTemplateConfig> {
  return (await apiRequest<ApiResponse<SourceTemplateConfig>>(`/reports/source-templates/${categoria}`)).data;
}

export async function setSourceTemplateDrive(categoria: SourceTemplateCategory, driveFileId: string): Promise<SourceTemplateConfig> {
  return (await apiRequest<ApiResponse<SourceTemplateConfig>>(`/reports/source-templates/${categoria}/drive`, {
    method: 'PUT',
    body: { driveFileId },
  })).data;
}

export async function setSourceTemplateUpload(categoria: SourceTemplateCategory, file: File): Promise<SourceTemplateConfig> {
  const formData = new FormData();
  formData.append('arquivo', file);
  const response = await apiUpload<ApiResponse<SourceTemplateConfig>>(`/reports/source-templates/${categoria}/upload`, formData);
  return response.data;
}

export async function removeSourceTemplate(categoria: SourceTemplateCategory): Promise<void> {
  await apiRequest<ApiResponse<null>>(`/reports/source-templates/${categoria}`, { method: 'DELETE' });
}

export async function generateReport(tipo: ReportType, formato: ReportFormat, competencia?: string, template?: string): Promise<GeneratedReport> {
  return (await apiRequest<ApiResponse<GeneratedReport>>('/reports/gerar', {
    method: 'POST',
    body: { tipo, formato, ...(competencia ? { competencia } : {}), ...(template ? { template } : {}) },
  })).data;
}

// Formatos office (docx/xlsx/pptx) sao gerados localmente e devolvidos como
// binario -- mesmo padrao de downloadDocumentFile em documentsService.ts.
function filenameFromContentDisposition(contentDisposition: string | null, fallback: string): string {
  const match = contentDisposition?.match(/filename="?([^"]+)"?/);
  return match ? match[1] : fallback;
}

export async function downloadReportFile(tipo: ReportType, formato: ReportFormat, competencia?: string, template?: string): Promise<void> {
  const { blob, contentDisposition } = await apiBlobWithHeaders('/reports/gerar', {
    method: 'POST',
    body: { tipo, formato, ...(competencia ? { competencia } : {}), ...(template ? { template } : {}) },
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
