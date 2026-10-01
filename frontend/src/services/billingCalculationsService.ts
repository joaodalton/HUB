import { apiBlobWithHeaders, apiRequest, apiUpload } from './apiClient';
import type { FaturaStatus } from './faturasService';

type ApiResponse<T> = { success: boolean; message: string; data: T };

const base = (empresaId: number) => `/platform/empresas/${empresaId}/billing-calculations`;

export type BillingClient = { id: number; nome: string };
export type BillingInvoice = {
  id: number;
  clientId: number;
  consumerUnitId: number | null;
  competencia: string | null;
  statusExtracao: string;
  statusValidacao: string;
  createdAt: string;
  clienteNome?: string | null;
  ucCodigo?: string | null;
  usinas?: Array<{ id: number; nome: string }>;
  valorTotalConcessionaria?: string | null;
  dataVencimento?: string | null;
  documentoId?: number | null;
  documentoDisponivel?: boolean;
  temPendencia?: boolean;
  contextualCharges?: Array<{
    id: number; statusInterno: string | null; asaasStatus: FaturaStatus; asaasId: string | null;
    valor: number; mesVencimento: string; boletoUrl: string | null;
  }>;
};
export type BillingInvoiceFilters = {
  q?: string; usinaId?: number; competencia?: string; statusProcessamento?: string;
  statusCobranca?: string; comPendencia?: boolean; page?: number; pageSize?: number;
};
export type BillingInvoicePage = {
  data: BillingInvoice[];
  pagination: { page: number; pageSize: number; total: number; pages: number };
};
export type BillingStage = {
  stage: string;
  status: string;
  timestamp: string | null;
  duration_ms: string | null;
  component: string;
  version: string | null;
  inputs: Record<string, unknown>;
  outputs: Record<string, unknown>;
  warnings: string[];
  blockers: string[];
};
export type BillingExecution = {
  id: number;
  empresaId: number;
  invoiceId: number;
  snapshotId: number | null;
  status: 'CALCULATED' | 'REVIEW_REQUIRED' | 'MISSING_DATA' | 'UNSUPPORTED' | 'ERROR';
  createdAt: string;
  durationMs?: string | null;
  blockedStage: string | null;
  blockers: string[];
  reused: boolean | null;
  auditoria?: { stages: BillingStage[] };
};
export type BillingSnapshot = {
  id: number;
  empresaId: number;
  invoiceId: number;
  fingerprint: string;
  regraSnapshot: Record<string, unknown>;
  entradaNormalizada: Record<string, unknown>;
  resultado: Record<string, unknown>;
  valorFinal: string;
  createdAt: string;
};
export type BillingUpload = { invoiceId: number; duplicate: boolean; invoice: Record<string, unknown> };

export async function getBillingClients(empresaId: number): Promise<BillingClient[]> {
  return (await apiRequest<ApiResponse<BillingClient[]>>(`${base(empresaId)}/clients`)).data;
}

function invoiceQuery(filters: BillingInvoiceFilters): string {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== '') params.set(key, String(value));
  });
  return params.size ? `?${params}` : '';
}

export async function getBillingInvoicePage(filters: BillingInvoiceFilters = {}, empresaId?: number): Promise<BillingInvoicePage> {
  const path = empresaId ? `${base(empresaId)}/invoices` : '/billing-calculations/invoices';
  const response = await apiRequest<ApiResponse<BillingInvoice[]> & Pick<BillingInvoicePage, 'pagination'>>(`${path}${invoiceQuery(filters)}`);
  return { data: response.data, pagination: response.pagination };
}

export async function getBillingInvoices(empresaId: number): Promise<BillingInvoice[]> {
  return (await getBillingInvoicePage({ pageSize: 100 }, empresaId)).data;
}

export async function getTenantBillingInvoices(): Promise<BillingInvoice[]> {
  return (await getBillingInvoicePage({ pageSize: 100 })).data;
}

export async function downloadBillingInvoice(invoiceId: number, empresaId?: number): Promise<void> {
  const path = empresaId
    ? `${base(empresaId)}/invoices/${invoiceId}/download`
    : `/billing-calculations/invoices/${invoiceId}/download`;
  const { blob, contentDisposition } = await apiBlobWithHeaders(path);
  const encodedName = contentDisposition?.match(/filename\*\s*=\s*UTF-8''([^;]+)/i)?.[1];
  const regularName = contentDisposition?.match(/filename\s*=\s*(?:"([^"]+)"|([^;]+))/i);
  let filename = regularName?.[1] ?? regularName?.[2] ?? '';
  if (encodedName) {
    try { filename = decodeURIComponent(encodedName); } catch { /* Keep the plain filename. */ }
  }
  filename = filename.replace(/[<>:"/\\|?*]/g, '_').replace(/\p{Cc}/gu, '_').trim().replace(/^\.+|\.+$/g, '').slice(0, 180);
  if (!filename) filename = `fatura-${invoiceId}.pdf`;
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export async function uploadTenantBillingInvoice(file: File): Promise<BillingUpload> {
  const body = new FormData();
  body.append('arquivo', file);
  return (await apiUpload<ApiResponse<BillingUpload>>('/billing-calculations/invoices/upload', body)).data;
}

export async function uploadBillingInvoice(empresaId: number, file: File): Promise<BillingUpload> {
  const body = new FormData();
  body.append('arquivo', file);
  return (await apiUpload<ApiResponse<BillingUpload>>(`${base(empresaId)}/invoices/upload`, body)).data;
}

export async function executeBillingCalculation(empresaId: number, invoiceId: number): Promise<BillingExecution> {
  return (await apiRequest<ApiResponse<BillingExecution>>(`${base(empresaId)}/invoices/${invoiceId}/execute`, { method: 'POST' })).data;
}

export async function getBillingExecutions(empresaId: number | undefined, invoiceId?: number): Promise<BillingExecution[]> {
  const query = invoiceId === undefined ? '' : `?invoiceId=${invoiceId}`;
  const path = empresaId ? base(empresaId) : '/billing-calculations';
  return (await apiRequest<ApiResponse<BillingExecution[]>>(`${path}${query}`)).data;
}

export async function getBillingExecution(empresaId: number | undefined, executionId: number): Promise<BillingExecution> {
  const path = empresaId ? base(empresaId) : '/billing-calculations';
  return (await apiRequest<ApiResponse<BillingExecution>>(`${path}/executions/${executionId}`)).data;
}

export async function getBillingSnapshot(empresaId: number, snapshotId: number): Promise<BillingSnapshot> {
  return (await apiRequest<ApiResponse<BillingSnapshot>>(`${base(empresaId)}/snapshots/${snapshotId}`)).data;
}
