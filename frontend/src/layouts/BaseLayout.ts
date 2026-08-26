import { createElement } from '../dom';
import { createHeader } from '../components/Header';
import { createLoading } from '../components/Loading';
import { createSidebar } from '../components/Sidebar';
import { createToastContainer } from '../components/Toast';

type BaseLayoutOptions = {
  content: HTMLElement;
  eyebrow?: string;
  title?: string;
};

export function createBaseLayout({ content, eyebrow, title }: BaseLayoutOptions): HTMLElement {
  const shell = createElement('div', { className: 'app-shell' });
  const body = createElement('div', { className: 'app-body' });
  const main = createElement('main', { className: 'app-main' });

  // Overlay para mobile
  const overlay = createElement('div', { className: 'sidebar-overlay' });
  overlay.addEventListener('click', () => {
    document.querySelector('.sidebar')?.classList.remove('open');
    overlay.classList.remove('active');
  });

  main.append(createHeader({ eyebrow, title }), content);
  const sidebar = createSidebar();
  body.append(sidebar, main);
  shell.append(overlay, body, createLoading(), createToastContainer());

  // Toggle do menu mobile
  const menuToggle = createElement('button', {
    className: 'mobile-menu-toggle',
    type: 'button',
    innerHTML: `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M3 12h18M3 6h18M3 18h18"/>
    </svg>`
  });

  menuToggle.addEventListener('click', () => {
    sidebar.classList.toggle('open');
    overlay.classList.toggle('active');
  });

  // Insere o toggle no header, depois do logo
  const header = main.querySelector('.masthead');
  if (header) {
    const mark = header.querySelector('.masthead-mark');
    if (mark) {
      mark.after(menuToggle);
    } else {
      header.insertBefore(menuToggle, header.firstChild);
    }
  }

  return shell;
}