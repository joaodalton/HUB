import { createElement, emptyState } from '../dom';
import { documentType, formattedDate, isFolder } from '../services/documentRules';
import type { DriveItem } from '../types';

type ResultsListOptions = {
  onToggleReserved: (item: DriveItem) => void;
  onOpenFolder: (item: DriveItem) => void;
  onBackFolder: () => void;
  isReserved: (item: DriveItem) => boolean;
};

export function createResultsPanel(options: ResultsListOptions): {
  element: HTMLElement;
  render: (items: DriveItem[]) => void;
  setFolderName: (name: string | null) => void;
  setLoading: () => void;
  setMessage: (message: string) => void;
  setCount: (count: number) => void;
} {
  const panel = createElement('section', { className: 'results-panel' });
  const title = createElement('div', { className: 'panel-title' });
  const titleText = createElement('div');
  const eyebrow = createElement('span', { className: 'eyebrow', textContent: 'Resultados' });
  const heading = createElement('h2', { textContent: 'Arquivos encontrados' });
  const counter = createElement('span', { className: 'counter', textContent: '0 itens' });
  const backButton = createElement('button', { className: 'secondary-button', textContent: 'Voltar', type: 'button' });
  const list = createElement('ul');
  list.id = 'resultados';

  titleText.append(eyebrow, heading);
  backButton.hidden = true;
  backButton.addEventListener('click', options.onBackFolder);
  title.append(titleText, counter, backButton);
  list.appendChild(emptyState('Digite algo para iniciar a busca.'));
  panel.append(title, list);

  function setCount(count: number): void {
    counter.textContent = `${count} ${count === 1 ? 'item' : 'itens'}`;
  }

  function setMessage(message: string): void {
    list.replaceChildren(emptyState(message));
    setCount(0);
  }

  function setLoading(): void {
    list.replaceChildren(createElement('li', { className: 'loading-state', textContent: 'Consultando arquivos...' }));
    setCount(0);
  }

  function setFolderName(name: string | null): void {
    heading.textContent = name ? `Conteudo: ${name}` : 'Arquivos encontrados';
    backButton.hidden = !name;
  }

  function render(items: DriveItem[]): void {
    list.replaceChildren();
    setCount(items.length);

    if (items.length === 0) {
      list.appendChild(emptyState('Nenhum documento encontrado para esse filtro.'));
      return;
    }

    items.forEach((item) => {
      const selected = options.isReserved(item);
      const row = createElement('li', { className: `result-row ${selected ? 'selected' : ''}`.trim() });
      const info = createElement('div', { className: 'result-info' });
      const link = createElement('a', { textContent: item.name });
      const meta = createElement('span', {
        className: 'result-meta',
        textContent: `${documentType(item)} - modificado em ${formattedDate(item)}`
      });
      const actions = createElement('div', { className: 'result-actions' });
      const openLink = isFolder(item)
        ? createElement('button', { className: 'small-button secondary-button', textContent: 'Ver conteudo', type: 'button' })
        : createElement('a', { className: 'small-button secondary-link', textContent: 'Abrir' });
      const toggle = createElement('button', {
        className: selected ? 'small-button remove-button' : 'small-button',
        textContent: selected ? 'Remover' : 'Reservar',
        type: 'button'
      });

      link.href = item.webViewLink;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';

      if (isFolder(item)) {
        openLink.addEventListener('click', () => options.onOpenFolder(item));
      } else {
        const externalLink = openLink as HTMLAnchorElement;
        externalLink.href = item.webViewLink;
        externalLink.target = '_blank';
        externalLink.rel = 'noopener noreferrer';
      }

      toggle.addEventListener('click', () => options.onToggleReserved(item));

      info.append(link, meta);
      actions.append(openLink, toggle);
      row.append(info, actions);
      list.appendChild(row);
    });
  }

  return { element: panel, render, setLoading, setMessage, setCount, setFolderName };
}
