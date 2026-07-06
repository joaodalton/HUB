import type { DriveItem } from './types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export async function searchDriveItems(term: string): Promise<DriveItem[]> {
  const response = await fetch(`${API_BASE_URL}/search?q=${encodeURIComponent(term)}`);

  if (!response.ok) {
    throw new Error('Falha ao buscar arquivos.');
  }

  return response.json() as Promise<DriveItem[]>;
}

export async function downloadReservedZip(items: DriveItem[]): Promise<Blob> {
  const response = await fetch(`${API_BASE_URL}/download-zip`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      ids: items.map((item) => item.id)
    })
  });

  if (!response.ok) {
    throw new Error('Falha ao baixar ZIP.');
  }

  return response.blob();
}
