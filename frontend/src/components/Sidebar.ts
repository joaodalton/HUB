import { createElement } from '../dom';
import { getCurrentUser, logout } from '../services/authService';
import { createIcon, type IconName } from './Icon';
import { getSettings } from '../services/settingsService';


type SidebarLink = {
  label: string;
  path: string;
  icon: IconName;
  // false = item do mockup que ainda nao tem pagina de verdade. Fica visivel
  // (organiza o mapa mental do menu final) mas nao navega, so "Em breve".
  enabled: boolean;
};

type SidebarSection = {
  title?: string;
  items: SidebarLink[];
};

// HUB ainda esta em V0.x (nucleo funcional incompleto, ver PROGRESS.md) --
// nao copiar numero de versao do mockup (v1.5.0), isso mentiria sobre o
// estado real do projeto pra quem olhar a tela.
export const HUB_VERSION = 'V1.x';

const sections: SidebarSection[] = [
  {
    items: [
      { label: 'Dashboard', path: '/dashboard', icon: 'dashboard', enabled: false }
    ]
  },
  {
    title: 'Gestão',
    items: [
      { label: 'Clientes', path: '/clientes', icon: 'clients', enabled: true },
      { label: 'Usinas', path: '/usinas', icon: 'plants', enabled: true },
      { label: 'UCs', path: '/ucs', icon: 'ucs', enabled: true },
      { label: 'Rateio', path: '/rateio', icon: 'rateio', enabled: true },
      { label: 'Documentos', path: '/documentos', icon: 'documents', enabled: true }
    ]
  },
  {
    title: 'Financeiro',
    items: [
      { label: 'Faturas', path: '/faturas', icon: 'faturas', enabled: false },
      { label: 'Pagamentos', path: '/pagamentos', icon: 'pagamentos', enabled: false },
      { label: 'Cobranças', path: '/cobrancas', icon: 'cobrancas', enabled: false }
    ]
  },
  {
    title: 'Automações',
    items: [
      { label: 'Pendências', path: '/pendencias', icon: 'pending', enabled: true },
      { label: 'Agenda', path: '/agenda', icon: 'agenda', enabled: true },
      { label: 'Templates', path: '/templates', icon: 'templates', enabled: false },
      { label: 'Mensagens', path: '/mensagens', icon: 'mensagens', enabled: false }
    ]
  },
  {
    title: 'Configurações',
    items: [
      { label: 'Integrações', path: '/integracoes', icon: 'integracoes', enabled: false },
      { label: 'Usuários', path: '/usuarios', icon: 'clients', enabled: true },
      { label: 'Permissões', path: '/permissoes', icon: 'permissoes', enabled: false },
      { label: 'Configurações', path: '/configuracoes', icon: 'settings', enabled: true }
    ]
  }
];

let brandTextElement: HTMLElement | null = null;

export function refreshSidebarBrand(): void { if (brandTextElement)
   {brandTextElement.textContent = getSettings().companyName || 'HUB';}}

export function createSidebar(): HTMLElement {
  const sidebar = createElement('aside', { className: 'sidebar' });
  const brand = createElement('div', { className: 'sidebar-brand' });
  const brandMark = createElement('span', { className: 'sidebar-mark', textContent: 'H' });
  brandTextElement = createElement('span', { textContent: getSettings().companyName || 'HUB' });
  const nav = createElement('nav', { className: 'sidebar-nav' });

  brand.append(brandMark, brandTextElement);

  const visibleSections = [...sections];
  if (getCurrentUser()?.isPlatformAdmin) {
    visibleSections.push({
      title: 'Plataforma',
      items: [{ label: 'Empresas', path: '/empresas', icon: 'clients', enabled: true }]
    });
  }

  visibleSections.forEach((section) => {
    const sectionElement = createElement('div', { className: 'sidebar-section' });

    if (section.title) {
      sectionElement.appendChild(createElement('span', {
        className: 'sidebar-section-title',
        textContent: section.title
      }));
    }

    section.items.forEach((item) => {
      sectionElement.appendChild(createSidebarLink(item));
    });

    nav.appendChild(sectionElement);
  });

  const footer = createElement('div', { className: 'sidebar-footer' });
  footer.append(createUserCard(), createVersionTag(), createLogoutButton());

  sidebar.append(brand, nav, footer);
  return sidebar;
}

function createSidebarLink(item: SidebarLink): HTMLElement {
  const icon = createIcon(item.icon, 'sidebar-icon');
  const label = createElement('span', { textContent: item.label });

  if (!item.enabled) {
    const disabledLink = createElement('span', { className: 'sidebar-link disabled' });
    disabledLink.title = 'Em breve';
    disabledLink.append(icon, label);
    return disabledLink;
  }

  const isActive = item.path === window.location.pathname
    || (window.location.pathname === '/' && item.path === '/documentos');
  const link = createElement('a', { className: isActive ? 'sidebar-link active' : 'sidebar-link' });

  link.href = item.path;
  link.append(icon, label);
  link.addEventListener('click', (event) => {
    event.preventDefault();
    window.history.pushState({}, '', item.path);
    window.dispatchEvent(new PopStateEvent('popstate'));
  });

  return link;
}

function createUserCard(): HTMLElement {
  const user = getCurrentUser();
  const card = createElement('div', { className: 'sidebar-user' });
  const avatar = createElement('span', {
    className: 'sidebar-user-avatar',
    textContent: initialsFor(user?.email ?? '?')
  });
  const text = createElement('div', { className: 'sidebar-user-text' });
  const name = createElement('span', { className: 'sidebar-user-name', textContent: user?.nome || user?.email || 'Usuário' });
  const role = createElement('span', {
    className: 'sidebar-user-role',
    textContent: user?.empresaNome || roleLabel(user?.role)
  });

  text.append(name, role);
  card.append(avatar, text);
  return card;
}

function createVersionTag(): HTMLElement {
  return createElement('span', { className: 'sidebar-version', textContent: `HUB ${HUB_VERSION}` });
}

function createLogoutButton(): HTMLElement {
  const logoutButton = createElement('button', {
    className: 'sidebar-logout',
    textContent: 'Sair',
    type: 'button'
  });

  logoutButton.addEventListener('click', () => {
    logout().finally(() => {
      window.history.pushState({}, '', '/login');
      window.dispatchEvent(new PopStateEvent('popstate'));
    });
  });

  return logoutButton;
}

function initialsFor(email: string): string {
  const name = email.split('@')[0] || '?';
  return name.slice(0, 2).toUpperCase();
}

function roleLabel(role?: string): string {
  const labels: Record<string, string> = {
    owner: 'Proprietário',
    admin: 'Administrador',
    operator: 'Operacional',
    financial: 'Financeiro',
    viewer: 'Visualizador'
  };
  return (role && labels[role]) || role || 'Usuário';
}
