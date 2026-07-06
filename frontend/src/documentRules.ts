import type { DriveItem, FilterKey } from './types';

export function isFolder(item: DriveItem): boolean {
  return item.mimeType.includes('folder');
}

export function documentType(item: DriveItem): string {
  if (isFolder(item)) return 'Pasta';

  const name = item.name.toLowerCase();

  if (name.includes('termo') || name.includes('adesao') || name.includes('adesão')) {
    return 'Termo de adesao';
  }

  if (name.includes('imagem') || name.includes('foto') || name.includes('vistoria')) {
    return 'Imagens em PDF';
  }

  return 'PDF';
}

export function matchesFilter(item: DriveItem, filter: FilterKey): boolean {
  const name = item.name.toLowerCase();

  if (filter === 'pastas') return isFolder(item);
  if (filter === 'termo') return name.includes('termo') || name.includes('adesao') || name.includes('adesão');
  if (filter === 'imagens') return name.includes('imagem') || name.includes('foto') || name.includes('vistoria');

  return true;
}

export function formattedDate(item: DriveItem): string {
  if (!item.modifiedTime) return '-';
  return new Date(item.modifiedTime).toLocaleDateString('pt-BR');
}
