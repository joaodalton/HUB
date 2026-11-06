import { apiBlob, apiRequest, apiUpload, fetchAllPages, type ApiResponse, type Pagination } from './apiClient';

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


type DocumentsFilter = { clienteId?: number; ucId?: number; plantId?: number };

function buildDocumentsQuery(filtro: DocumentsFilter, page?: number, pageSize?: number): string {
  const params = new URLSearchParams();
  if (filtro.clienteId) params.set('clienteId', String(filtro.clienteId));
  if (filtro.ucId) params.set('ucId', String(filtro.ucId));
  if (filtro.plantId) params.set('plantId', String(filtro.plantId));
  if (page) params.set('page', String(page));
  if (pageSize) params.set('pageSize', String(pageSize));
  const query = params.toString();
  return query ? `?${query}` : '';
}

export type DocumentsPage = { data: DocumentRow[]; pagination: Pagination };

export async function getDocumentsPage(filtro: DocumentsFilter = {}, page = 1, pageSize = 50): Promise<DocumentsPage> {
  const response = await apiRequest<ApiResponse<DocumentRow[]> & Pick<DocumentsPage, 'pagination'>>(
    `/documents${buildDocumentsQuery(filtro, page, pageSize)}`
  );
  return { data: response.data, pagination: response.pagination };
}

// Lista completa (todas as paginas) -- mantido pra quem precisa de todos os
// documentos do filtro (ex.: painel do cliente), sem expor paginacao a
// esses consumidores.
export async function getDocuments(clienteId?: number, ucId?: number, plantId?: number): Promise<DocumentRow[]> {
  const filtro: DocumentsFilter = { clienteId, ucId, plantId };
  return fetchAllPages((page, pageSize) => getDocumentsPage(filtro, page, pageSize));
}

export async function uploadDocument(
  data: { clienteId?: number; ucId?: number; plantId?: number; categoriaId?: number; nome?: string },
  file: File
): Promise<DocumentRow> {
  const formData = new FormData();
  formData.append('arquivo', file);
  if (data.categoriaId) formData.append('categoriaId', String(data.categoriaId));
  if (data.clienteId) formData.append('clienteId', String(data.clienteId));
  if (data.ucId) formData.append('ucId', String(data.ucId));
  if (data.plantId) formData.append('plantId', String(data.plantId));
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
