import { createElement, emptyState } from '../dom';
import { createIcon } from './Icon';
import { documentType, isFolder } from '../services/documentRules';
import { t } from '../services/i18nService';
import type { DriveItem } from '../types';

type ReservedPanelOptions = {
  onRemove: (item: DriveItem) => void;
  onClear: () => void;
  onOpenAll: () => void;
  onDownloadZip: () => void;
  onLinkToClient: () => void;
};

export function createReservedPanel(options: ReservedPanelOptions): {
  element: HTMLElement;
  render: (items: DriveItem[]) => void;
  setDownloading: (isDownloading: boolean) => void;
} {
  const panel = createElement('aside', { className: 'reserved-panel' });
  const title = createElement('div', { className: 'panel-title' });
  const titleText = createElement('div');
  const eyebrow = createElement('span', { className: 'eyebrow', textContent: t('documents.reserved.eyebrow') });
  const heading = createElement('h2', { textContent: t('documents.reserved.heading') });
  const counter = createElement('span', { className: 'counter', textContent: `0 ${t('documents.results.itemPlural')}` });
  const list = createElement('ul');
  const actions = createElement('div', { className: 'reserved-actions' });
  const downloadButton = createElement('button', { textContent: t('documents.reserved.downloadZip'), type: 'button' });
  const linkButton = createElement('button', { textContent: t('documents.reserved.linkToClient'), type: 'button' });
  const openAllButton = createElement('button', { textContent: t('documents.reserved.openAll'), type: 'button' });
  const clearButton = createElement('button', {
    className: 'secondary-button',
    textContent: t('documents.reserved.clearSelection'),
    type: 'button'
  });

  list.id = 'reservados';
  titleText.append(eyebrow, heading);
  title.append(titleText, counter);
  actions.append(downloadButton, linkButton, openAllButton, clearButton);
  panel.append(title, list, actions);

  downloadButton.addEventListener('click', options.onDownloadZip);
  linkButton.addEventListener('click', options.onLinkToClient);
  openAllButton.addEventListener('click', options.onOpenAll);
  clearButton.addEventListener('click', options.onClear);

  function setDownloading(isDownloading: boolean): void {
    downloadButton.textContent = isDownloading ? t('documents.reserved.downloading') : t('documents.reserved.downloadZip');
    downloadButton.disabled = isDownloading;
  }

  function render(items: DriveItem[]): void {
    const downloadableCount = items.filter((item) => !isFolder(item)).length;

    list.replaceChildren();
    counter.textContent = `${items.length} ${items.length === 1 ? t('documents.results.itemSingular') : t('documents.results.itemPlural')}`;
    downloadButton.disabled = downloadableCount === 0;
    linkButton.disabled = downloadableCount === 0;
    openAllButton.disabled = items.length === 0;
    clearButton.disabled = items.length === 0;

    if (items.length === 0) {
      list.appendChild(emptyState(t('documents.reserved.empty'), true));
      return;
    }

    items.forEach((item) => {
      const row = createElement('li', { className: 'reserved-row' });
      const info = createElement('div', { className: 'reserved-info' });
      const link = createElement('a', { textContent: item.name });
      const meta = createElement('span', { textContent: documentType(item) });
      const remove = createElement('button', { className: 'icon-button', type: 'button' });

      remove.appendChild(createIcon('x'));

      link.href = item.webViewLink;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';

      remove.setAttribute('aria-label', `${t('documents.reserved.removeAriaPrefix')} ${item.name}`);
      remove.addEventListener('click', () => options.onRemove(item));

      info.append(link, meta);
      row.append(info, remove);
      list.appendChild(row);
    });
  }

  return { element: panel, render, setDownloading };
}
