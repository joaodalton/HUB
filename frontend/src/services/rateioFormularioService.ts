import { apiBlob, apiRequest } from './apiClient';

export type FormularioLinha = {
  ordem: number;
  nome: string;
  documento: string | null;
  ucIdentificacao: string | null;
  percentual: number;
  termoAdesaoOk: boolean;
  clienteId: number | null;
  ucId: number | null;
};

export type FormularioTabela = {
  plantId: number;
  plantNome: string;
  ucGeradora: string | null;
  ucAncora: string | null;
  empresaNome: string;
  empresaCnpj: string | null;
  empresaEmail: string | null;
  documentoCnpjOk: boolean;
  documentoEstatutoOk: boolean;
  linhas: FormularioLinha[];
  somaPercentual: number;
  excedeLimiteLinhas: boolean;
};

export type VerificarDocumentosResultado = {
  ok: boolean;
  faltando: Array<{ clienteId: number | null; ucId: number | null; nome: string }>;
};

export async function getFormularioTabela(plantId: number): Promise<FormularioTabela> {
  const response = await apiRequest<{ success: boolean; message: string; data: FormularioTabela }>(
    `/rateio/formulario?plantId=${plantId}`
  );
  return response.data;
}

export async function verificarDocumentosFormulario(plantId: number): Promise<VerificarDocumentosResultado> {
  const response = await apiRequest<{ success: boolean; message: string; data: VerificarDocumentosResultado }>(
    '/rateio/formulario/verificar-documentos',
    { method: 'POST', body: { plantId } }
  );
  return response.data;
}

// As 2 funcoes abaixo baixam PDF binario -- nao usam apiRequest (que espera
// JSON), seguem o mesmo padrao de apiBlob usado em documentsService.ts.
async function baixarPdf(path: string, body: unknown): Promise<Blob> {
  return apiBlob(path, { method: 'POST', body });
}

export function gerarFormularioPdf(
  plantId: number,
  responsavelNome: string,
  responsavelCpf: string,
  linhas: FormularioLinha[]
): Promise<Blob> {
  return baixarPdf('/rateio/formulario/gerar-pdf', { plantId, responsavelNome, responsavelCpf, linhas });
}

export function gerarTermosAdesaoPdf(plantId: number): Promise<Blob> {
  return baixarPdf('/rateio/formulario/gerar-termos', { plantId });
}
