import './styles.css';

import { downloadReservedZip, searchDriveItems } from './api';
import { createElement } from './dom';
import { isFolder, matchesFilter } from './documentRules';
import { createReservedPanel } from './components/ReservedPanel';
import { createResultsPanel } from './components/ResultsList';
import { createSearchPanel } from './components/SearchPanel';
import type { DriveItem, FilterKey } from './types';

let currentFilter: FilterKey = 'todos';
let currentResults: DriveItem[] = [];
const reservedItems = new Map<string, DriveItem>();

const app = document.querySelector<HTMLDivElement>('#app');

if (!app) {
  throw new Error('Elemento #app nao encontrado.');
}

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

const page = createElement('div', { className: 'page' });
page.append(createCorners(), createHeader(), createWorkspace());
app.appendChild(page);
renderReserved();

function createCorners(): DocumentFragment {
  const fragment = document.createDocumentFragment();
  ['tl', 'tr', 'bl', 'br'].forEach((position) => {
    fragment.appendChild(createElement('div', { className: `corner corner-${position}` }));
  });
  return fragment;
}

function createHeader(): HTMLElement {
  const header = createElement('header', { className: 'masthead' });
  const mark = createElement('div', { className: 'masthead-mark', textContent: 'HUB' });
  const text = createElement('div', { className: 'masthead-text' });
  const eyebrow = createElement('span', { className: 'eyebrow', textContent: 'Central de documentos' });
  const heading = createElement('h1', { textContent: 'Busque, separe e abra arquivos do Drive' });

  text.append(eyebrow, heading);
  header.append(mark, text);
  return header;
}

function createWorkspace(): HTMLElement {
  const workspace = createElement('main', { className: 'workspace' });
  const mainColumn = createElement('section', { className: 'main-column' });

  mainColumn.append(searchPanel, resultsPanel.element);
  workspace.append(mainColumn, reservedPanel.element);
  return workspace;
}

async function runSearch(term: string): Promise<void> {
  if (!term) {
    currentResults = [];
    resultsPanel.setMessage('Digite algo para iniciar a busca.');
    return;
  }

  resultsPanel.setLoading();

  try {
    currentResults = await searchDriveItems(term);
    renderResults();
  } catch {
    currentResults = [];
    resultsPanel.setMessage('Nao foi possivel conectar ao servidor. Verifique se o backend esta rodando.');
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
  } catch {
    alert('Nao foi possivel baixar o ZIP. Verifique se o backend esta rodando.');
  } finally {
    reservedPanel.setDownloading(false);
    renderReserved();
  }
}
