import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../layouts/BaseLayout', () => ({
  createBaseLayout: ({ content }: { content: HTMLElement }) => content,
}));

vi.mock('../services/clientsService', () => ({
  getClients: vi.fn(),
}));

vi.mock('../services/documentsService', () => ({
  getDocuments: vi.fn(),
}));

vi.mock('../services/driveService', () => ({
  searchDriveItems: vi.fn(),
  listDriveFolder: vi.fn(),
  listDriveRoot: vi.fn(),
  downloadReservedZip: vi.fn(),
}));

import { getClients } from '../services/clientsService';
import { getDocuments } from '../services/documentsService';
import { listDriveFolder, listDriveRoot } from '../services/driveService';
import { createDocumentsPage } from '../pages/DocumentsPage';

async function flush(): Promise<void> {
  await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
}

const rootFolder = {
  id: 'folder-1', name: 'Clientes', mimeType: 'application/vnd.google-apps.folder', webViewLink: 'https://drive/folder-1'
};

describe('DocumentsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getClients).mockResolvedValue([]);
    vi.mocked(getDocuments).mockResolvedValue([]);
  });
  afterEach(() => { vi.restoreAllMocks(); });

  it('opens the Drive root folder from the tree root label', async () => {
    vi.mocked(listDriveRoot).mockResolvedValue([rootFolder]);
    const content = createDocumentsPage();
    await flush();

    const rootLabel = Array.from(content.querySelectorAll('button')).find((item) => item.textContent === 'Drive');
    expect(rootLabel).toBeInstanceOf(HTMLButtonElement);
    rootLabel?.click();
    await flush();

    expect(listDriveRoot).toHaveBeenCalledTimes(2);
    expect(content.textContent).toContain('Clientes');
    expect(content.textContent).toContain('Conteudo: Pasta raiz do Drive');
  });

  it('returns to the root listing when going back from a root subfolder', async () => {
    vi.mocked(listDriveRoot).mockResolvedValue([rootFolder]);
    vi.mocked(listDriveFolder).mockResolvedValue([]);
    const content = createDocumentsPage();
    await flush();

    const rootLabel = Array.from(content.querySelectorAll('button')).find((item) => item.textContent === 'Drive');
    rootLabel?.click();
    await flush();

    const openButton = Array.from(content.querySelectorAll('button')).find((item) => item.textContent === 'Ver conteudo');
    openButton?.click();
    await flush();
    expect(listDriveFolder).toHaveBeenCalledWith('folder-1');

    const backButton = Array.from(content.querySelectorAll('button')).find((item) => item.textContent === 'Voltar');
    expect(backButton).toBeInstanceOf(HTMLButtonElement);
    backButton?.click();
    await flush();

    expect(listDriveRoot).toHaveBeenCalledTimes(3);
    expect(content.textContent).toContain('Conteudo: Pasta raiz do Drive');
  });
});
