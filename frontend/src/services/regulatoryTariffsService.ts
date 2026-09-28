import { apiRequest, apiUpload } from './apiClient';

type ApiResponse<T> = { success: boolean; data: T };

export type RegulatoryTariffStatus = {
  status: 'missing' | 'updated'; records: number; coverage: { from: string | null; until: string | null };
  lastImport: { id: number; completedAt: string | null; sourceVersion: string; records: number; createdById: number } | null;
};
export type RegulatoryTariffPreview = {
  previewId: number; expiresAt: string; status: 'ready' | 'invalid'; validos: number; ignorados: number;
  duplicados: number; conflitos: number; rejeitados: number;
  linhas: Array<{ linha: number | null; situacao: string; motivo?: string | null; official_distributor?: string; component?: string; valid_from?: string; valid_until?: string; value_kwh?: string }>;
  ckan?: { resourceId: string; generatedAt?: string | null; found: number };
};

export async function getRegulatoryTariffStatus(): Promise<RegulatoryTariffStatus> {
  return (await apiRequest<ApiResponse<RegulatoryTariffStatus>>('/regulatory-tariffs/status')).data;
}
export async function previewRegulatoryTariffs(file: File, sourceUrl: string): Promise<RegulatoryTariffPreview> {
  const form = new FormData(); form.append('arquivo', file);
  form.append('sourceUrl', sourceUrl);
  return (await apiUpload<ApiResponse<RegulatoryTariffPreview>>('/regulatory-tariffs/imports/preview', form)).data;
}
export async function previewRegulatoryTariffsFromCkan(distributor: string, year: number): Promise<RegulatoryTariffPreview> {
  return (await apiRequest<ApiResponse<RegulatoryTariffPreview>>('/regulatory-tariffs/imports/ckan/preview', {
    method: 'POST', body: { distributor, year }
  })).data;
}
export async function confirmRegulatoryTariffs(previewId: number): Promise<{ created: number; unchanged: number }> {
  return (await apiRequest<ApiResponse<{ created: number; unchanged: number }>>('/regulatory-tariffs/imports/confirm', { method: 'POST', body: { previewId } })).data;
}
