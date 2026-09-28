import { apiUpload } from './apiClient';

type ApiResponse<T> = { success: boolean; message: string; data: T };

export type PdfDiagnosticStage = {
  stage: string;
  status: string;
  timestamp: string | null;
  durationMs: string | null;
  component: string | null;
  version: string | null;
  inputs: Record<string, unknown>;
  outputs: Record<string, unknown>;
  warnings: unknown[];
  blockers: unknown[];
};

export type PdfDiagnostic = {
  executionId: string | null;
  status: string;
  extractionStatus: string;
  normalizationStatus: string;
  billingEligibility: { status: string; eligible: boolean; reason: string | null };
  pdf: Record<string, unknown>;
  extracted: unknown;
  normalized: unknown;
  compensations: unknown;
  missingFields: string[];
  warnings: unknown[];
  blockers: unknown[];
  stages: PdfDiagnosticStage[];
  durationMs: string | null;
  error?: unknown;
};

export async function analyzeBillingPdf(file: File): Promise<PdfDiagnostic> {
  const body = new FormData();
  body.append('arquivo', file);
  return (await apiUpload<ApiResponse<PdfDiagnostic>>('/platform/billing-diagnostics/pdf', body)).data;
}
