import { createElement } from '../dom';
import { t } from '../services/i18nService';

export type SearchPanelEvents = {
  onSearch: (term: string) => void;
};

export function createSearchPanel(events: SearchPanelEvents): {
  element: HTMLElement;
} {
  const panel = createElement('section', { className: 'search-panel' });

  const label = createElement('label', { className: 'search-label', textContent: t('shared.searchPanel.searchLabel') });
  label.htmlFor = 'busca';

  const row = createElement('div', { className: 'search-row' });
  const input = createElement('input');
  input.id = 'busca';
  input.type = 'text';
  input.placeholder = t('shared.searchPanel.searchPlaceholder');
  input.autocomplete = 'off';

  const button = createElement('button', { textContent: t('shared.searchPanel.searchButton'), type: 'button' });

  const runSearch = () => events.onSearch(input.value.trim());
  button.addEventListener('click', runSearch);
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') runSearch();
  });

  row.append(input, button);

  const hint = createElement('p', {
    className: 'search-hint',
    textContent: t('shared.searchPanel.hint')
  });

  panel.append(label, row, hint);

  return { element: panel };
}
