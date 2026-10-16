import { apiRequest, type ApiResponse } from './apiClient';

export type ReportType = 'cadastro' | 'financeiro' | 'rateio';
export type ReportFormat = 'doc' | 'sheet' | 'slide';
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
