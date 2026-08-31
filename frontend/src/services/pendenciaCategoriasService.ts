// frontend/src/services/pendenciaCategoriasService.ts
// Categorias extras de Pendencia, criadas pelo usuario na hora (alem das 6
// padrao em CATEGORIAS_PADRAO/pendenciasService.ts). Guardadas na tabela
// Setting generica (mesma chave/valor que Aparencia ja usa via /settings) --
// decisao deliberada pra nao precisar de tabela/rota nova no backend agora.
import { apiRequest } from './apiClient';

const SETTINGS_KEY = 'pendenciaCategoriasExtras';

type ApiResponse<T> = {
  success: boolean;
  message: string;
  data: T;
};

export async function getExtraCategorias(): Promise<string[]> {
  const response = await apiRequest<ApiResponse<Record<string, string>>>('/settings');
  return parseExtras(response.data[SETTINGS_KEY]);
}

// Recebe a lista atual (o chamador ja tem em memoria, ver PendenciasPage.ts)
// em vez de buscar de novo -- evita uma chamada GET extra e mantem a pagina
// como fonte unica da verdade durante a sessao.
export async function addExtraCategoria(nome: string, atuais: string[]): Promise<string[]> {
  const trimmed = nome.trim();

  if (!trimmed || atuais.includes(trimmed)) return atuais;

  const next = [...atuais, trimmed];
  await apiRequest<ApiResponse<Record<string, string>>>('/settings', {
    method: 'PUT',
    body: { [SETTINGS_KEY]: JSON.stringify(next) }
  });

  return next;
}

function parseExtras(raw: string | undefined): string[] {
  if (!raw) return [];

  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((item): item is string => typeof item === 'string') : [];
  } catch {
    return [];
  }
}