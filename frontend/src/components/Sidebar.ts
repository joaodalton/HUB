import { createElement } from '../dom';
import { logout } from '../services/authService';

const menuItems = [
  { label: 'Documentos', path: '/documentos', icon: '📁' },
  { label: 'Clientes', path: '/clientes', icon: '👥' },
  { label: 'UCs', path: '/ucs', icon: '🔌' },
  { label: 'Usinas', path: '/usinas', icon: '⚡' },
  { label: 'Pendencias', path: '/pendencias', icon: '🕒' },
  { label: 'Agenda', path: '/agenda', icon: '📅' },
  { label: 'Configuracoes', path: '/configuracoes', icon: '⚙️' }
];

export function createSidebar(): HTMLElement {
  const sidebar = createElement('aside', { className: 'sidebar' });
  const brand = createElement('div', { className: 'sidebar-brand' });
  const brandMark = createElement('span', { className: 'sidebar-mark', textContent: 'H' });
  const brandText = createElement('span', { textContent: 'HUB' });
  const nav = createElement('nav', { className: 'sidebar-nav' });
  const logoutButton = createElement('button', {
    className: 'sidebar-logout',
    textContent: 'Sair',
    type: 'button'
  });

  brand.append(brandMark, brandText);

  menuItems.forEach((item) => {
    const isActive = item.path === window.location.pathname || (window.location.pathname === '/' && item.path === '/documentos');
    const link = createElement('a', {
      className: isActive ? 'sidebar-link active' : 'sidebar-link'
    });
    const icon = createElement('span', { className: 'sidebar-icon', textContent: item.icon });
    const label = createElement('span', { textContent: item.label });

    link.href = item.path;
    link.append(icon, label);
    link.addEventListener('click', (event) => {
      event.preventDefault();
      window.history.pushState({}, '', item.path);
      window.dispatchEvent(new PopStateEvent('popstate'));
    });
    nav.appendChild(link);
  });

  logoutButton.addEventListener('click', () => {
    logout();
    window.history.pushState({}, '', '/login');
    window.dispatchEvent(new PopStateEvent('popstate'));
  });

  sidebar.append(brand, nav, logoutButton);
  return sidebar;
}