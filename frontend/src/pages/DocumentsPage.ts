import { createReservedPanel } from '../components/ReservedPanel';
import { createResultsPanel } from '../components/ResultsList';
import { createSearchPanel } from '../components/SearchPanel';
import { createElement } from '../dom';
import { useGlobalLoading } from '../hooks/useGlobalLoading';
import { useToast } from '../hooks/useToast';
import { createBaseLayout } from '../layouts/BaseLayout';
import { downloadReservedZip, searchDriveItems } from '../services/driveService';
import { isFolder, matchesFilter } from '../services/documentRules';
import type { DriveItem, FilterKey } from '../types';

export function createDocumentsPage(): HTMLElement {
  let currentFilter: FilterKey = 'todos';
  let currentResults: DriveItem[] = [];
  const reservedItems = new Map<string, DriveItem>();
  const loading = useGlobalLoading();
  const toast = useToast();

  const resultsPanel = createResultsPanel({
    isReserved: (item) => reservedItems.has(item.id),
    onToggleReserved: toggleReserved
  });

  const reservedPanel = createReservedPanel({
    onRemove: toggleReserved,
    onClear: clearReserved,
    onOpenAll: openAllReserved,
    onDownloadZip: downloadZip
  });

  const searchPanel = createSearchPanel({
    onSearch: runSearch,
    onFilterChange: (filter) => {
      currentFilter = filter;
      renderResults();
    }
  });

  const workspace = createElement('section', { className: 'workspace' });
  const mainColumn = createElement('section', { className: 'main-column' });

  mainColumn.append(searchPanel, resultsPanel.element);
  workspace.append(mainColumn, reservedPanel.element);
  renderReserved();

  return createBaseLayout({
    content: workspace,
    eyebrow: 'Central de documentos',
    title: 'Busque, separe e abra arquivos do Drive'
  });

  async function runSearch(term: string): Promise<void> {
    if (!term) {
      currentResults = [];
      resultsPanel.setMessage('Digite algo para iniciar a busca.');
      return;
    }

    resultsPanel.setLoading();
    loading.show();

    try {
      currentResults = await searchDriveItems(term);
      renderResults();
    } catch {
      currentResults = [];
      resultsPanel.setMessage('Nao foi possivel conectar ao servidor. Verifique se o backend esta rodando.');
      toast.error('Nao foi possivel conectar ao servidor.');
    } finally {
      loading.hide();
    }
  }

  function renderResults(): void {
    resultsPanel.render(currentResults.filter((item) => matchesFilter(item, currentFilter)));
  }

  function renderReserved(): void {
    reservedPanel.render(Array.from(reservedItems.values()));
  }

  function toggleReserved(item: DriveItem): void {
    if (reservedItems.has(item.id)) {
      reservedItems.delete(item.id);
    } else {
      reservedItems.set(item.id, item);
    }

    renderResults();
    renderReserved();
  }

  function clearReserved(): void {
    reservedItems.clear();
    renderResults();
    renderReserved();
  }

  function openAllReserved(): void {
    reservedItems.forEach((item) => {
      window.open(item.webViewLink, '_blank', 'noopener,noreferrer');
    });
  }

  async function downloadZip(): Promise<void> {
    const files = Array.from(reservedItems.values()).filter((item) => !isFolder(item));

    if (files.length === 0) return;

    reservedPanel.setDownloading(true);
    loading.show();

    try {
      const blob = await downloadReservedZip(files);
      const url = URL.createObjectURL(blob);
      const link = createElement('a');

      link.href = url;
      link.download = 'hub-reservados.zip';
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      toast.success('ZIP gerado com sucesso.');
    } catch {
      toast.error('Nao foi possivel baixar o ZIP. Verifique se o backend esta rodando.');
    } finally {
      reservedPanel.setDownloading(false);
      loading.hide();
      renderReserved();
    }
  }
}
