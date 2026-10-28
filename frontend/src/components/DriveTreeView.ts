import { createElement, emptyState } from '../dom';
import { isFolder } from '../services/documentRules';
import { listDriveFolder, listDriveRoot } from '../services/driveService';
import type { DriveItem } from '../types';

type DriveTreeViewOptions = {
  onSelectFolder: (folder: DriveItem) => void;
  onOpenRoot: () => void;
  onError?: (message: string) => void;
};

type NodeState = {
  expanded: boolean;
  children?: DriveItem[];
  loading: boolean;
};

export function createDriveTreeView(options: DriveTreeViewOptions): { element: HTMLElement } {
  const panel = createElement('nav', { className: 'drive-tree' });
  panel.setAttribute('aria-label', 'Arvore de pastas do Drive');

  const rootToggle = createElement('button', { className: 'drive-tree-toggle', type: 'button', textContent: '▼' });
  const rootLabel = createElement('button', { className: 'drive-tree-root-label', type: 'button', textContent: 'Drive' });
  const rootRow = createElement('div', { className: 'drive-tree-row drive-tree-root-row' });
  const list = createElement('ul', { className: 'drive-tree-list' });

  rootRow.append(rootToggle, rootLabel);
  panel.append(rootRow, list);

  // cache simples por folder.id -- so busca filhos uma vez por sessao da pagina.
  const cache = new Map<string, NodeState>();
  let rootExpanded = true;
  let rootItems: DriveItem[] = [];
  let rootLoaded = false;

  rootLabel.addEventListener('click', () => options.onOpenRoot());
  rootToggle.addEventListener('click', () => {
    rootExpanded = !rootExpanded;
    render();
  });

  void loadRoot();

  async function loadRoot(): Promise<void> {
    list.replaceChildren(createElement('li', { className: 'loading-state', textContent: 'Carregando...' }));
    try {
      rootItems = await listDriveRoot();
      rootLoaded = true;
      render();
    } catch {
      const message = 'Nao foi possivel carregar a pasta raiz do Drive.';
      list.replaceChildren(emptyState(message, true));
      options.onError?.(message);
    }
  }

  function render(): void {
    if (!rootLoaded) return;

    rootToggle.textContent = rootExpanded ? '▼' : '▶';
    list.replaceChildren();

    if (!rootExpanded) return;

    if (rootItems.length === 0) {
      list.appendChild(emptyState('Pasta raiz vazia.', true));
      return;
    }

    rootItems.forEach((item) => list.appendChild(renderNode(item, 1)));
  }

  function renderNode(item: DriveItem, depth: number): HTMLLIElement {
    const li = createElement('li', { className: 'drive-tree-node' });
    const row = createElement('div', { className: 'drive-tree-row' });
    row.style.paddingLeft = `${depth * 16}px`;

    if (!isFolder(item)) {
      const link = createElement('a', { className: 'drive-tree-file', textContent: item.name });
      link.href = item.webViewLink;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      row.appendChild(link);
      li.appendChild(row);
      return li;
    }

    const state = cache.get(item.id) ?? { expanded: false, loading: false };
    cache.set(item.id, state);

    const toggle = createElement('button', {
      className: 'drive-tree-toggle',
      type: 'button',
      textContent: state.expanded ? '▼' : '▶'
    });
    const label = createElement('button', { className: 'drive-tree-folder-label', textContent: item.name, type: 'button' });
    const childrenList = createElement('ul', { className: 'drive-tree-list' });

    label.addEventListener('click', () => options.onSelectFolder(item));
    toggle.addEventListener('click', () => void toggleNode(item.id, state, childrenList));

    row.append(toggle, label);
    li.append(row, childrenList);

    if (state.expanded && state.children) {
      if (state.children.length === 0) {
        childrenList.appendChild(emptyState('Pasta vazia.', true));
      } else {
        state.children.forEach((child) => childrenList.appendChild(renderNode(child, depth + 1)));
      }
    }

    return li;
  }

  async function toggleNode(folderId: string, state: NodeState, childrenList: HTMLUListElement): Promise<void> {
    if (state.loading) return;

    if (state.expanded) {
      state.expanded = false;
      childrenList.replaceChildren();
      render();
      return;
    }

    if (state.children) {
      state.expanded = true;
      render();
      return;
    }

    state.loading = true;
    childrenList.replaceChildren(createElement('li', { className: 'loading-state', textContent: 'Carregando...' }));

    try {
      state.children = await listDriveFolder(folderId);
      state.expanded = true;
    } catch {
      const message = 'Nao foi possivel abrir a pasta. Tente novamente.';
      childrenList.replaceChildren(emptyState(message, true));
      options.onError?.(message);
      state.loading = false;
      return;
    }

    state.loading = false;
    render();
  }

  return { element: panel };
}
