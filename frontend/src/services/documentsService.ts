import { apiBlob, apiRequest, apiUpload } from './apiClient';

export type DocumentRow = {
  id: number;
  nome: string;
  clienteId: number | null;
  ucId: number | null;
  categoriaId: number;
  categoria: string | null;
  storageProvider: string;
  storageRef: string | null;
  mimeType: string | null;
};

export type CategoryRow = {
  id: number;
  nome: string;
  tipo: string | null;
  descricao: string | null;
};

type ApiResponse<T> = {
  success: boolean;
  message: string;
  data: T;
};

export async function getDocuments(clienteId?: number, ucId?: number): Promise<DocumentRow[]> {
  const params = new URLSearchParams();
  if (clienteId) params.set('clienteId', String(clienteId));
  if (ucId) params.set('ucId', String(ucId));

  const query = params.toString();
  const response = await apiRequest<ApiResponse<DocumentRow[]>>(`/documents${query ? `?${query}` : ''}`);
  return response.data;
}

export async function uploadDocument(
  data: { clienteId?: number; ucId?: number; categoriaId?: number; nome?: string },
  file: File
): Promise<DocumentRow> {
  const formData = new FormData();
  formData.append('arquivo', file);
  if (data.categoriaId) formData.append('categoriaId', String(data.categoriaId));
  if (data.clienteId) formData.append('clienteId', String(data.clienteId));
  if (data.ucId) formData.append('ucId', String(data.ucId));
  if (data.nome) formData.append('nome', data.nome);

  const response = await apiUpload<ApiResponse<DocumentRow>>('/documents', formData);
  return response.data;
}

// Vincula um arquivo que ja esta no Google Drive a um cliente/UC sem fazer upload --
// so cria o registro em Document apontando pro fileId do Drive (storageProvider='google_drive').
export async function linkDriveDocument(data: {
  clienteId: number;
  categoriaId: number;
  nome: string;
  driveFileId: string;
  ucId?: number;
  mimeType?: string;
}): Promise<DocumentRow> {
  const response = await apiRequest<ApiResponse<DocumentRow>>('/documents/drive-link', {
    method: 'POST',
    body: data
  });
  return response.data;
}

export async function renameDocument(id: number, nome: string): Promise<DocumentRow> {
  const response = await apiRequest<ApiResponse<DocumentRow>>(`/documents/${id}`, {
    method: 'PUT',
    body: { nome }
  });
  return response.data;
}

export async function deleteDocument(id: number): Promise<void> {
  await apiRequest<ApiResponse<null>>(`/documents/${id}`, { method: 'DELETE' });
}

// Baixa via fetch autenticado (Bearer token) e dispara o download no navegador --
// um <a href> direto pra /documents/<id>/download daria 401, essa rota nao e publica.
export async function downloadDocumentFile(id: number, filename: string): Promise<void> {
  const blob = await apiBlob(`/documents/${id}/download`);
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');

  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export async function getCategories(): Promise<CategoryRow[]> {
  const response = await apiRequest<ApiResponse<CategoryRow[]>>('/categories');
  return response.data;
}

export async function createCategory(nome: string): Promise<CategoryRow> {
  const response = await apiRequest<ApiResponse<CategoryRow>>('/categories', {
    method: 'POST',
    body: { nome }
  });
  return response.data;
}
