import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../services/driveService', () => ({
  listDriveRoot: vi.fn(),
  listDriveFolder: vi.fn()
}));

import { listDriveFolder, listDriveRoot } from '../services/driveService';
import { createDriveTreeView } from '../components/DriveTreeView';

async function flush(): Promise<void> {
  await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
}

const folder = {
  id: 'folder-1', name: 'Clientes', mimeType: 'application/vnd.google-apps.folder', webViewLink: 'https://drive/folder-1'
};

const file = {
  id: 'file-1', name: 'contrato.pdf', mimeType: 'application/pdf', webViewLink: 'https://drive/file-1'
};

describe('DriveTreeView', () => {
  beforeEach(() => { vi.clearAllMocks(); });
  afterEach(() => { vi.restoreAllMocks(); });

  it('loads the root on mount', async () => {
    vi.mocked(listDriveRoot).mockResolvedValue([folder, file]);
    const { element } = createDriveTreeView({ onSelectFolder: vi.fn(), onOpenRoot: vi.fn() });
    await flush();

    expect(listDriveRoot).toHaveBeenCalledTimes(1);
    expect(element.textContent).toContain('Clientes');
    expect(element.textContent).toContain('contrato.pdf');
  });

  it('expands a folder and loads its children only once (lazy + cache)', async () => {
    vi.mocked(listDriveRoot).mockResolvedValue([folder]);
    vi.mocked(listDriveFolder).mockResolvedValue([file]);
    const { element } = createDriveTreeView({ onSelectFolder: vi.fn(), onOpenRoot: vi.fn() });
    await flush();

    expect(listDriveFolder).not.toHaveBeenCalled();

    const toggle = element.querySelectorAll('.drive-tree-toggle')[1] as HTMLButtonElement;
    toggle.click();
    await flush();

    expect(listDriveFolder).toHaveBeenCalledTimes(1);
    expect(listDriveFolder).toHaveBeenCalledWith('folder-1');
    expect(element.textContent).toContain('contrato.pdf');

    toggle.click(); // recolhe
    await flush();
    expect(element.textContent).not.toContain('contrato.pdf');

    const toggleAgain = element.querySelectorAll('.drive-tree-toggle')[1] as HTMLButtonElement;
    toggleAgain.click(); // expande de novo, mesma sessao
    await flush();

    expect(listDriveFolder).toHaveBeenCalledTimes(1);
    expect(element.textContent).toContain('contrato.pdf');
  });

  it('shows an empty-folder message when a folder has no children', async () => {
    vi.mocked(listDriveRoot).mockResolvedValue([folder]);
    vi.mocked(listDriveFolder).mockResolvedValue([]);
    const { element } = createDriveTreeView({ onSelectFolder: vi.fn(), onOpenRoot: vi.fn() });
    await flush();

    const toggle = element.querySelectorAll('.drive-tree-toggle')[1] as HTMLButtonElement;
    toggle.click();
    await flush();

    expect(element.textContent).toContain('Pasta vazia.');
  });

  it('reports an error via onError when expanding a folder fails, instead of looking empty', async () => {
    vi.mocked(listDriveRoot).mockResolvedValue([folder]);
    vi.mocked(listDriveFolder).mockRejectedValue(new Error('network error'));
    const onError = vi.fn();
    const { element } = createDriveTreeView({ onSelectFolder: vi.fn(), onOpenRoot: vi.fn(), onError });
    await flush();

    const toggle = element.querySelectorAll('.drive-tree-toggle')[1] as HTMLButtonElement;
    toggle.click();
    await flush();

    expect(onError).toHaveBeenCalledTimes(1);
    expect(element.textContent).toContain('Nao foi possivel abrir a pasta');
  });

  it('clicking a folder name triggers onSelectFolder', async () => {
    vi.mocked(listDriveRoot).mockResolvedValue([folder]);
    const onSelectFolder = vi.fn();
    const { element } = createDriveTreeView({ onSelectFolder, onOpenRoot: vi.fn() });
    await flush();

    const label = Array.from(element.querySelectorAll('button')).find((item) => item.textContent === 'Clientes');
    label?.click();

    expect(onSelectFolder).toHaveBeenCalledWith(folder);
  });

  it('clicking a file does not trigger onSelectFolder', async () => {
    vi.mocked(listDriveRoot).mockResolvedValue([file]);
    const onSelectFolder = vi.fn();
    const { element } = createDriveTreeView({ onSelectFolder, onOpenRoot: vi.fn() });
    await flush();

    const link = element.querySelector('.drive-tree-file') as HTMLAnchorElement;
    expect(link).toBeInstanceOf(HTMLAnchorElement);
    link.click();

    expect(onSelectFolder).not.toHaveBeenCalled();
  });
});
