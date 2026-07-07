import { createElement } from '../dom';

const loadingState = {
  element: null as HTMLElement | null
};

export function createLoading(): HTMLElement {
  const overlay = createElement('div', { className: 'global-loading', textContent: 'Carregando...' });
  overlay.hidden = true;
  loadingState.element = overlay;
  return overlay;
}

export function setGlobalLoading(isLoading: boolean): void {
  if (!loadingState.element) return;
  loadingState.element.hidden = !isLoading;
}
