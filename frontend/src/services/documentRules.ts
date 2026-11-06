import type { DriveItem } from '../types';

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