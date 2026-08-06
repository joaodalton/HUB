import type { DriveItem, FilterKey } from '../types';

const MIME_TYPE_LABELS: Record<string, string> = {
  'application/pdf': 'PDF',
  'image/jpeg': 'Imagem (JPEG)',
  'image/png': 'Imagem (PNG)',
  'application/vnd.google-apps.document': 'Documento Google',
  'application/vnd.google-apps.spreadsheet': 'Planilha Google'
};

export function isFolder(item: DriveItem): boolean {
  return item.mimeType.includes('folder');
}

export function documentType(item: DriveItem): string {
  if (isFolder(item)) return 'Pasta';

  const name = normalizedText(item.name);

  // Precisa das DUAS palavras -- "ficha de adesao" tem "adesao" mas nao "termo",
  // e nao pode entrar aqui (bug reportado: filtro pegava ficha junto com termo).
  if (name.includes('termo') && name.includes('adesao')) {
    return 'Termo de adesao';
  }

  if (name.includes('imagem') || name.includes('foto') || name.includes('vistoria')) {
    return 'Imagens em PDF';
  }

  return 'PDF';
}

export function matchesFilter(item: DriveItem, filter: FilterKey): boolean {
  const name = normalizedText(item.name);

  if (filter === 'pastas') return isFolder(item);
  if (filter === 'termo') return name.includes('termo') && name.includes('adesao');
  if (filter === 'imagens') return name.includes('imagem') || name.includes('foto') || name.includes('vistoria');

  return true;
}

// Rotulo por tipo de arquivo (mimeType), usado pelo filtro dinamico de "Tipo" --
// as opcoes desse filtro no SearchPanel sao montadas em cima do que essa funcao
// devolve para os resultados atuais, nao um enum fixo no codigo.
export function fileTypeLabel(item: DriveItem): string {
  if (isFolder(item)) return 'Pasta';
  return MIME_TYPE_LABELS[item.mimeType] ?? 'Outro';
}

export function matchesType(item: DriveItem, tipo: string): boolean {
  return tipo === 'todos' || fileTypeLabel(item) === tipo;
}

export function matchesDateRange(item: DriveItem, from: string, to: string): boolean {
  if (!from && !to) return true;
  if (!item.modifiedTime) return false;

  const modified = item.modifiedTime.slice(0, 10); // YYYY-MM-DD, mesmo formato dos <input type="date">

  if (from && modified < from) return false;
  if (to && modified > to) return false;

  return true;
}

export function formattedDate(item: DriveItem): string {
  if (!item.modifiedTime) return '-';
  return new Date(item.modifiedTime).toLocaleDateString('pt-BR');
}

function normalizedText(value: string): string {
  return value
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '');
}