import { createElement } from '../dom';

type ToastType = 'success' | 'error' | 'warning' | 'info';

const toastIcons: Record<ToastType, string> = { success: '\u2713', error: '\u00d7', warning: '!', info: 'i' };

const toastState = {
  container: null as HTMLElement | null
};

export function createToastContainer(): HTMLElement {
  const container = createElement('div', { className: 'toast-container' });
  container.setAttribute('aria-live', 'polite');
  container.setAttribute('aria-atomic', 'true');
  toastState.container = container;
  return container;
}

export function showToast(message: string, type: ToastType = 'info'): void {
  if (!toastState.container) return;

  const toast = createElement('div', {
    className: `toast toast-${type}`
  });
  toast.setAttribute('role', type === 'error' ? 'alert' : 'status');
  toast.append(
    createElement('span', { className: 'toast-symbol', textContent: toastIcons[type] }),
    createElement('span', { className: 'toast-message', textContent: message })
  );

  toastState.container.appendChild(toast);
  window.setTimeout(() => toast.remove(), 4200);
}
