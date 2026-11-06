import { createElement } from '../dom';
import { createHeader } from '../components/Header';
import { createIcon, type IconName } from '../components/Icon';
import { createLoading } from '../components/Loading';
import { createToastContainer } from '../components/Toast';
import { getCurrentUser, logout } from '../services/authService';

type PlatformLayoutOptions = { content: HTMLElement; title: string; description?: string };

const links: Array<{ label: string; path: string; icon: IconName }> = [
  { label: 'Visão geral', path: '/platform', icon: 'dashboard' },
  { label: 'Empresas', path: '/platform/companies', icon: 'clients' }
];

export function createPlatformLayout({ content, title, description }: PlatformLayoutOptions): HTMLElement {
  const shell = createElement('div', { className: 'app-shell platform-shell' });
  const body = createElement('div', { className: 'app-body' });
  const sidebar = createElement('aside', { className: 'sidebar platform-sidebar' });
  const brand = createElement('div', { className: 'sidebar-brand platform-brand' });
  brand.append(createElement('span', { className: 'sidebar-mark', textContent: 'H' }), createElement('span', { textContent: 'HUB PLATFORM' }));
  const nav = createElement('nav', { className: 'sidebar-nav' });
  const section = createElement('div', { className: 'sidebar-section' });
  section.appendChild(createElement('span', { className: 'sidebar-section-title', textContent: 'Plataforma' }));
  links.forEach((item) => {
    const active = window.location.pathname === item.path;
    const link = createElement('a', { className: active ? 'sidebar-link active' : 'sidebar-link' });
    link.href = item.path;
    link.append(createIcon(item.icon, 'sidebar-icon'), createElement('span', { textContent: item.label }));
    link.addEventListener('click', (event) => navigate(event, item.path));
    section.appendChild(link);
  });
  nav.appendChild(section);
  const footer = createElement('div', { className: 'sidebar-footer' });
  const user = getCurrentUser();
  footer.append(createElement('span', { className: 'sidebar-version', textContent: user?.nome || user?.email || 'Platform Admin' }));
  const exit = createElement('button', { className: 'sidebar-logout', type: 'button' });
  exit.append(createIcon('login'), createElement('span', { className: 'sidebar-logout-label', textContent: 'Sair' }));
  exit.addEventListener('click', () => void logout().finally(() => go('/login')));
  footer.appendChild(exit);
  sidebar.append(brand, nav, footer);

  const main = createElement('main', { className: 'app-main' });
  main.append(createHeader({ eyebrow: 'HUB Platform', title, description }), content);
  body.append(sidebar, main);
  shell.append(body, createLoading(), createToastContainer());
  return shell;
}

function navigate(event: Event, path: string): void { event.preventDefault(); go(path); }
function go(path: string): void {
  window.history.pushState({}, '', path);
  window.dispatchEvent(new PopStateEvent('popstate'));
}
