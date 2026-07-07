import { createElement } from '../dom';

type ToastType = 'success' | 'error' | 'info';

const toastState = {
  container: null as HTMLElement | null
};

export function createToastContainer(): HTMLElement {
  const container = createElement('div', { className: 'toast-container' });
  container.setAttribute('aria-live', 'polite');
  toastState.container = container;
  return container;
}

export function showToast(message: string, type: ToastType = 'info'): void {
  if (!toastState.container) return;

  const toast = createElement('div', {
    className: `toast toast-${type}`,
    textContent: message
  });

  toastState.container.appendChild(toast);
  window.setTimeout(() => toast.remove(), 4200);
}
