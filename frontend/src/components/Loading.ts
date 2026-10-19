import { createElement } from '../dom';

const loadingState = {
  element: null as HTMLElement | null,
  timeoutId: null as ReturnType<typeof setTimeout> | null
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

  if (isLoading) {
    // Timeout de segurança: após 2s, esconde o loading automaticamente
    // caso a página esqueça de chamar loading.hide()
    if (loadingState.timeoutId) {
      clearTimeout(loadingState.timeoutId);
    }
    loadingState.timeoutId = setTimeout(() => {
      if (loadingState.element && !loadingState.element.hidden) {
        loadingState.element.hidden = true;
      }
      loadingState.timeoutId = null;
    }, 2000);
  } else {
    // Hide manual cancela o timeout
    if (loadingState.timeoutId) {
      clearTimeout(loadingState.timeoutId);
      loadingState.timeoutId = null;
    }
  }
}
