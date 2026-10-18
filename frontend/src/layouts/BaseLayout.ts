import { createElement } from '../dom';
import { createHeader } from '../components/Header';
import { createLoading } from '../components/Loading';
import { createSidebar } from '../components/Sidebar';
import { createToastContainer } from '../components/Toast';
import { createCommandPalette } from '../components/CommandPalette';
import { createIcon } from '../components/Icon';
import { getCurrentUser, refreshCurrentUser } from '../services/authService';
import { sairDaVisualizacao } from '../services/platformService';
import { invalidateSettingsCache } from '../services/settingsService';

type BaseLayoutOptions = {
  content: HTMLElement;
  eyebrow?: string;
  title?: string;
  description?: string;
};

const SIDEBAR_PREFERENCE_KEY = 'hub_sidebar_collapsed';

export function createBaseLayout({ content, eyebrow, title, description }: BaseLayoutOptions): HTMLElement {
  const shell = createElement('div', { className: 'app-shell' });
  const body = createElement('div', { className: 'app-body' });
  const main = createElement('main', { className: 'app-main' });

  // Overlay para mobile
  const overlay = createElement('div', { className: 'sidebar-overlay' });

  const header = createHeader({ eyebrow, title, description });
  const palette = createCommandPalette();
  header.appendChild(palette.trigger);
  const contextBanner = createPlatformContextBanner();
  main.append(header);
  if (contextBanner) main.appendChild(contextBanner);
  main.appendChild(content);
  const sidebar = createSidebar();
  sidebar.id = 'app-sidebar';
  const sidebarToggle = createElement('button', {
    className: 'sidebar-collapse-toggle icon-button',
    type: 'button'
  });
  sidebarToggle.setAttribute('aria-controls', sidebar.id);
  sidebar.prepend(sidebarToggle);

  let sidebarCollapsed = window.localStorage.getItem(SIDEBAR_PREFERENCE_KEY) === 'true';

  function applySidebarPreference(): void {
    shell.classList.toggle('sidebar-collapsed', sidebarCollapsed);
    sidebarToggle.textContent = sidebarCollapsed ? '»' : '«';
    sidebarToggle.title = sidebarCollapsed ? 'Expandir menu lateral' : 'Recolher menu lateral';
    sidebarToggle.setAttribute('aria-label', sidebarToggle.title);
    sidebarToggle.setAttribute('aria-expanded', String(!sidebarCollapsed));
  }

  sidebarToggle.addEventListener('click', () => {
    sidebarCollapsed = !sidebarCollapsed;
    window.localStorage.setItem(SIDEBAR_PREFERENCE_KEY, String(sidebarCollapsed));
    applySidebarPreference();
  });
  applySidebarPreference();
  body.append(sidebar, main);
  shell.append(overlay, body, palette.element, createLoading(), createToastContainer());

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
      const links = [...sidebar.querySelectorAll<HTMLElement>('a.sidebar-link, button')]
        .filter((element) => element.offsetParent !== null);
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
  const masthead = main.querySelector('.masthead');
  if (masthead) {
    masthead.insertBefore(menuToggle, masthead.firstChild);
  }

  return shell;
}

function createPlatformContextBanner(): HTMLElement | null {
  const user = getCurrentUser();
  if (!user?.isPlatformAdmin || !user.platformViewEmpresaId) return null;
  const banner = createElement('section', { className: 'platform-context-banner' });
  banner.setAttribute('role', 'status');
  const text = createElement('div');
  text.append(
    createElement('strong', { textContent: 'PLATFORM ADMIN' }),
    createElement('span', { textContent: `Empresa atual: ${user.platformViewEmpresaNome || `#${user.platformViewEmpresaId}`}` })
  );
  const exit = createElement('button', { className: 'secondary-button button-with-icon', type: 'button' });
  exit.append(createIcon('login'), document.createTextNode('Sair da empresa'));
  exit.addEventListener('click', () => {
    exit.disabled = true;
    void sairDaVisualizacao()
      .then(() => refreshCurrentUser())
      .then(() => {
        invalidateSettingsCache();
        window.dispatchEvent(new CustomEvent('hub:tenant-context-changed'));
        window.history.pushState({}, '', '/platform');
        window.dispatchEvent(new PopStateEvent('popstate'));
      })
      .catch(() => { exit.disabled = false; });
  });
  banner.append(text, exit);
  return banner;
}
