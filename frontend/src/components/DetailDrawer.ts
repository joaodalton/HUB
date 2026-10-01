import { createElement } from '../dom';

export type DetailDrawerTab = { label: string; content: HTMLElement };

export type DetailDrawerProps = {
  title: string;
  badge?: HTMLElement;
  tabs?: DetailDrawerTab[];
  onClose: () => void;
  actions?: HTMLElement[];
};

export function createDetailDrawer({ title, badge, tabs = [], onClose, actions = [] }: DetailDrawerProps): HTMLElement {
  const overlay = createElement('div', { className: 'detail-drawer-overlay' });
  const drawer = createElement('aside', { className: 'detail-drawer' });
  const header = createElement('header', { className: 'detail-drawer-header' });
  const heading = createElement('h2', { textContent: title });
  const close = createElement('button', { className: 'icon-button neutral', textContent: '×', type: 'button', title: 'Fechar' });
  const body = createElement('div', { className: 'detail-drawer-body' });
  const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  const titleId = `drawer-${Date.now()}-${Math.random().toString(16).slice(2)}`;

  heading.id = titleId;
  drawer.setAttribute('role', 'dialog');
  drawer.setAttribute('aria-modal', 'true');
  drawer.setAttribute('aria-labelledby', titleId);

  const closeDrawer = () => {
    document.removeEventListener('keydown', handleKeyDown);
    onClose();
    previousFocus?.focus();
  };
  const handleKeyDown = (event: KeyboardEvent) => {
    if (event.key === 'Escape') closeDrawer();
    if (event.key !== 'Tab') return;
    const items = Array.from(drawer.querySelectorAll<HTMLElement>('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')).filter((item) => !item.hasAttribute('disabled'));
    if (!items.length) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  };

  close.setAttribute('aria-label', 'Fechar painel');
  close.addEventListener('click', closeDrawer);
  header.append(heading, ...(badge ? [badge] : []), close);
  if (tabs.length > 0) {
    const tabList = createElement('div', { className: 'detail-drawer-tabs' });
    tabs.forEach((tab, index) => {
      const button = createElement('button', { className: index === 0 ? 'detail-tab active' : 'detail-tab', textContent: tab.label, type: 'button' });
      button.addEventListener('click', () => {
        tabList.querySelectorAll('button').forEach((item) => item.classList.remove('active'));
        button.classList.add('active');
        body.replaceChildren(tab.content);
      });
      tabList.appendChild(button);
    });
    drawer.appendChild(tabList);
    body.appendChild(tabs[0].content);
  }
  drawer.append(header, body, ...actions);
  overlay.addEventListener('click', (event) => { if (event.target === overlay) closeDrawer(); });
  overlay.appendChild(drawer);
  document.addEventListener('keydown', handleKeyDown);
  window.setTimeout(() => close.focus());
  return overlay;
}
