import { createElement } from '../dom';

export type ModalParts = { overlay: HTMLElement; dialog: HTMLElement; body: HTMLElement; close: () => void };

export function createModalShell(title: string, eyebrow?: string, onClose?: () => void): ModalParts {
  const overlay = createElement('section', { className: 'modal-overlay' });
  const dialog = createElement('article', { className: 'plant-card hub-modal' });
  const header = createElement('div', { className: 'modal-header' });
  const headingWrap = createElement('div');
  const heading = createElement('h2', { textContent: title });
  const body = createElement('div', { className: 'modal-body' });
  const closeButton = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Fechar' });
  const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  const titleId = `hub-modal-${Date.now()}-${Math.random().toString(16).slice(2)}`;

  heading.id = titleId;
  dialog.setAttribute('role', 'dialog');
  dialog.setAttribute('aria-modal', 'true');
  dialog.setAttribute('aria-labelledby', titleId);
  if (eyebrow) headingWrap.appendChild(createElement('span', { className: 'eyebrow', textContent: eyebrow }));
  headingWrap.appendChild(heading);
  header.append(headingWrap, closeButton);
  dialog.append(header, body);
  overlay.appendChild(dialog);

  const close = () => {
    document.removeEventListener('keydown', onKeyDown);
    overlay.remove();
    onClose?.();
    previousFocus?.focus();
  };
  const focusables = () => Array.from(dialog.querySelectorAll<HTMLElement>('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')).filter((item) => !item.hasAttribute('disabled'));
  const onKeyDown = (event: KeyboardEvent) => {
    if (event.key === 'Escape') close();
    if (event.key !== 'Tab') return;
    const items = focusables();
    if (!items.length) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  };

  closeButton.addEventListener('click', close);
  overlay.addEventListener('click', (event) => { if (event.target === overlay) close(); });
  document.addEventListener('keydown', onKeyDown);
  window.setTimeout(() => closeButton.focus());
  return { overlay, dialog, body, close };
}
