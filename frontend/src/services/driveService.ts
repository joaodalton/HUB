import type { DriveItem } from '../types';
import { apiBlob, apiRequest } from './apiClient';

export function searchDriveItems(term: string): Promise<DriveItem[]> {
  return apiRequest<DriveItem[]>(`/search?q=${encodeURIComponent(term)}`);
}

export function downloadReservedZip(items: DriveItem[]): Promise<Blob> {
  return apiBlob('/download-zip', {
    method: 'POST',
    body: {
      ids: items.map((item) => item.id)
    }
  });
}
