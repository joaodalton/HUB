import { createDocumentLinkModal } from '../components/DocumentLinkModal';
import { createReservedPanel } from '../components/ReservedPanel';
import { createResultsPanel } from '../components/ResultsList';
import { createSearchPanel } from '../components/SearchPanel';
import { createElement } from '../dom';
import { useGlobalLoading } from '../hooks/useGlobalLoading';
import { useToast } from '../hooks/useToast';
import { createBaseLayout } from '../layouts/BaseLayout';
import { getClients, type ClientRow } from '../services/clientsService';
import { fileTypeLabel, isFolder, matchesDateRange, matchesFilter, matchesType } from '../services/documentRules';
import { downloadReservedZip, searchDriveItems } from '../services/driveService';
import type { DriveItem, FilterKey } from '../types';

export function createDocumentsPage(): HTMLElement {
  let currentFilter: FilterKey = 'todos';
  let currentType = 'todos';
  let dateFrom = '';
  let dateTo = '';
  let currentResults: DriveItem[] = [];
  let clients: ClientRow[] = [];
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
    onDownloadZip: downloadZip,
    onLinkToClient: openLinkModal
  });

  const searchPanel = createSearchPanel({
    onSearch: runSearch,
    onFilterChange: (filter) => {
      currentFilter = filter;
      renderResults();
    },
    onTypeChange: (tipo) => {
      currentType = tipo;
      renderResults();
    },
    onDateRangeChange: (from, to) => {
      dateFrom = from;
      dateTo = to;
      renderResults();
    }
  });

  const workspace = createElement('section', { className: 'workspace' });
  const mainColumn = createElement('section', { className: 'main-column' });

  mainColumn.append(searchPanel.element, resultsPanel.element);
  workspace.append(mainColumn, reservedPanel.element);
  renderReserved();
  loadClients();

  return createBaseLayout({
    content: workspace,
    eyebrow: 'Central de documentos',
    title: 'Busque, separe e abra arquivos do Drive'
  });

  async function loadClients(): Promise<void> {
    try {
      clients = await getClients();
    } catch {
      clients = [];
    }
  }

  async function runSearch(term: string): Promise<void> {
    if (!term) {
      currentResults = [];
      resultsPanel.setMessage('Digite algo para iniciar a busca.');
      searchPanel.updateTypeOptions([]);
      return;
    }

    resultsPanel.setLoading();
    loading.show();

    try {
      currentResults = await searchDriveItems(term);
      searchPanel.updateTypeOptions(Array.from(new Set(currentResults.map(fileTypeLabel))));
      renderResults();
    } catch (error) {
      currentResults = [];
      const message = error instanceof Error ? error.message : 'Nao foi possivel pesquisar documentos.';
      resultsPanel.setMessage(message);
      toast.error(message);
    } finally {
      loading.hide();
    }
  }

  function renderResults(): void {
    resultsPanel.render(currentResults.filter((item) =>
      matchesFilter(item, currentFilter) &&
      matchesType(item, currentType) &&
      matchesDateRange(item, dateFrom, dateTo)
    ));
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

  function openLinkModal(): void {
    const files = Array.from(reservedItems.values()).filter((item) => !isFolder(item));

    if (files.length === 0) {
      toast.error('Reserve pelo menos um arquivo (nao uma pasta) antes de vincular a um cliente.');
      return;
    }

    document.body.appendChild(createDocumentLinkModal({
      files,
      clients,
      onLinked: (linkedIds) => {
        linkedIds.forEach((id) => reservedItems.delete(id));
        renderResults();
        renderReserved();
        toast.success(linkedIds.length === 1 ? 'Documento vinculado ao cliente.' : `${linkedIds.length} documentos vinculados ao cliente.`);
      },
      onError: (message) => toast.error(message)
    }));
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
