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

  close.addEventListener('click', onClose);
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
  overlay.addEventListener('click', (event) => { if (event.target === overlay) onClose(); });
  overlay.appendChild(drawer);
  return overlay;
}
