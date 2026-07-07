import { createElement, emptyState } from '../dom';
import { documentType, isFolder } from '../services/documentRules';
import type { DriveItem } from '../types';

type ReservedPanelOptions = {
  onRemove: (item: DriveItem) => void;
  onClear: () => void;
  onOpenAll: () => void;
  onDownloadZip: () => void;
};

export function createReservedPanel(options: ReservedPanelOptions): {
  element: HTMLElement;
  render: (items: DriveItem[]) => void;
  setDownloading: (isDownloading: boolean) => void;
} {
  const panel = createElement('aside', { className: 'reserved-panel' });
  const title = createElement('div', { className: 'panel-title' });
  const titleText = createElement('div');
  const eyebrow = createElement('span', { className: 'eyebrow', textContent: 'Reservados' });
  const heading = createElement('h2', { textContent: 'Separados para usar' });
  const counter = createElement('span', { className: 'counter', textContent: '0 itens' });
  const list = createElement('ul');
  const actions = createElement('div', { className: 'reserved-actions' });
  const downloadButton = createElement('button', { textContent: 'Baixar ZIP', type: 'button' });
  const openAllButton = createElement('button', { textContent: 'Abrir todos', type: 'button' });
  const clearButton = createElement('button', {
    className: 'secondary-button',
    textContent: 'Limpar selecao',
    type: 'button'
  });

  list.id = 'reservados';
  titleText.append(eyebrow, heading);
  title.append(titleText, counter);
  actions.append(downloadButton, openAllButton, clearButton);
  panel.append(title, list, actions);

  downloadButton.addEventListener('click', options.onDownloadZip);
  openAllButton.addEventListener('click', options.onOpenAll);
  clearButton.addEventListener('click', options.onClear);

  function setDownloading(isDownloading: boolean): void {
    downloadButton.textContent = isDownloading ? 'Baixando...' : 'Baixar ZIP';
    downloadButton.disabled = isDownloading;
  }

  function render(items: DriveItem[]): void {
    const downloadableCount = items.filter((item) => !isFolder(item)).length;

    list.replaceChildren();
    counter.textContent = `${items.length} ${items.length === 1 ? 'item' : 'itens'}`;
    downloadButton.disabled = downloadableCount === 0;
    openAllButton.disabled = items.length === 0;
    clearButton.disabled = items.length === 0;

    if (items.length === 0) {
      list.appendChild(emptyState('Nenhum arquivo reservado ainda.', true));
      return;
    }

    items.forEach((item) => {
      const row = createElement('li', { className: 'reserved-row' });
      const info = createElement('div', { className: 'reserved-info' });
      const link = createElement('a', { textContent: item.name });
      const meta = createElement('span', { textContent: documentType(item) });
      const remove = createElement('button', { className: 'icon-button', textContent: 'x', type: 'button' });

      link.href = item.webViewLink;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';

      remove.setAttribute('aria-label', `Remover ${item.name}`);
      remove.addEventListener('click', () => options.onRemove(item));

      info.append(link, meta);
      row.append(info, remove);
      list.appendChild(row);
    });
  }

  return { element: panel, render, setDownloading };
}
