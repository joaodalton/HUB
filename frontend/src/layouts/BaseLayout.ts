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

  main.append(createHeader({ eyebrow, title }), content);
  const sidebar = createSidebar();
  sidebar.id = 'app-sidebar';
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
  menuToggle.setAttribute('aria-label', 'Abrir menu');
  menuToggle.setAttribute('aria-controls', sidebar.id);
  menuToggle.setAttribute('aria-expanded', 'false');

  function setMenuOpen(open: boolean, restoreFocus = true): void {
    sidebar.classList.toggle('open', open);
    overlay.classList.toggle('active', open);
    menuToggle.setAttribute('aria-expanded', String(open));
    menuToggle.setAttribute('aria-label', open ? 'Fechar menu' : 'Abrir menu');
    main.inert = open;
    if (open) sidebar.querySelector<HTMLElement>('a.sidebar-link')?.focus();
    else if (restoreFocus) menuToggle.focus();
  }

  const desktop = window.matchMedia('(min-width: 769px)');
  const onViewportChange = (): void => {
    if (!shell.isConnected) {
      desktop.removeEventListener('change', onViewportChange);
      return;
    }
    if (desktop.matches && sidebar.classList.contains('open')) setMenuOpen(false, false);
  };
  desktop.addEventListener('change', onViewportChange);

  overlay.addEventListener('click', () => setMenuOpen(false));

  menuToggle.addEventListener('click', () => {
    setMenuOpen(!sidebar.classList.contains('open'));
  });
  shell.addEventListener('keydown', (event) => {
    if (event.key === 'Tab' && sidebar.classList.contains('open')) {
      const links = [...sidebar.querySelectorAll<HTMLElement>('a.sidebar-link, button')];
      const first = links[0];
      const last = links[links.length - 1];
      if (first && last && (event.shiftKey ? document.activeElement === first : document.activeElement === last)) {
        event.preventDefault();
        (event.shiftKey ? last : first).focus();
      }
    }
    if (event.key === 'Escape' && sidebar.classList.contains('open')) {
      setMenuOpen(false);
    }
  });

  // Insere o toggle no header
  const header = main.querySelector('.masthead');
  if (header) {
    header.insertBefore(menuToggle, header.firstChild);
  }

  return shell;
}
