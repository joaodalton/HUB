export type FilterKey = 'todos' | 'pastas' | 'imagens' | 'termo';

export type DriveItem = {
  id: string;
  name: string;
  mimeType: string;
  webViewLink: string;
  iconLink?: string;
  modifiedTime?: string;
};
