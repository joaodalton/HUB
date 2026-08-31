import { apiRequest, apiUpload } from './apiClient';

type ApiResponse<T> = { success: boolean; message: string; data: T };

export type ImportacaoContagens = {
  clientes: number;
  ucs: number;
  usinas: number;
};

export type ImportacaoProblema = {
  tipo: string;
  linha: number;
  erro: string;
};

export type ImportacaoPrevia = {
  previewId: number;
  expiraEm: string;
  contagens: ImportacaoContagens;
  erros: ImportacaoProblema[];
};

export type ImportacaoResultado = ImportacaoContagens;

/** Upload apenas cria uma prévia no backend; nada é persistido até confirmar. */
export async function criarPreviaImportacao(arquivo: File, tipoCsv?: 'clientes' | 'ucs' | 'usinas'): Promise<ImportacaoPrevia> {
  const formData = new FormData();
  formData.append('arquivo', arquivo);
  if (tipoCsv) formData.append('tipo', tipoCsv);
  const response = await apiUpload<ApiResponse<ImportacaoPrevia>>('/importacoes/preview', formData);
  return response.data;
}

/** Confirma exatamente a prévia já validada pelo backend. */
export async function confirmarImportacao(importacaoId: number): Promise<ImportacaoResultado> {
  const response = await apiRequest<ApiResponse<ImportacaoResultado>>(`/importacoes/${encodeURIComponent(importacaoId)}/confirmar`, { method: 'POST' });
  return response.data;
}
