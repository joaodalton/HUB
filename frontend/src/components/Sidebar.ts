import { createElement } from '../dom';
import { getCurrentUser, logout } from '../services/authService';
import { createIcon, type IconName } from './Icon';
import { createLogoMark } from './LogoMark';
import { getSettings } from '../services/settingsService';
import { t } from '../services/i18nService';


type SidebarLink = {
  labelKey: string;
  path: string;
  icon: IconName;
  // false = item do mockup que ainda nao tem pagina de verdade. Fica visivel
  // (organiza o mapa mental do menu final) mas nao navega, so "Em breve".
  enabled: boolean;
};

type SidebarSection = {
  titleKey?: string;
  items: SidebarLink[];
};

// HUB ainda esta em V0.x (nucleo funcional incompleto, ver PROGRESS.md) --
// nao copiar numero de versao do mockup (v1.5.0), isso mentiria sobre o
// estado real do projeto pra quem olhar a tela.
export const HUB_VERSION = 'V1.x';

function buildSections(): SidebarSection[] {
  return [
    {
      titleKey: 'nav.section.operacao',
      items: [
        { labelKey: 'nav.item.clientes', path: '/clientes', icon: 'clients', enabled: true },
        { labelKey: 'nav.item.ucs', path: '/ucs', icon: 'ucs', enabled: true },
        { labelKey: 'nav.item.usinas', path: '/usinas', icon: 'plants', enabled: true },
        { labelKey: 'nav.item.rateio', path: '/rateio', icon: 'rateio', enabled: true },
        { labelKey: 'nav.item.documentos', path: '/documentos', icon: 'documents', enabled: true }
      ]
    },
    {
      titleKey: 'nav.section.financeiro',
      items: [
        { labelKey: 'nav.item.financeiro', path: '/financeiro', icon: 'pagamentos', enabled: true },
        { labelKey: 'nav.item.faturas', path: '/faturas', icon: 'faturas', enabled: true },
        { labelKey: 'nav.item.regrasCobranca', path: '/regras-cobranca', icon: 'cobrancas', enabled: true },
        { labelKey: 'nav.item.relatorios', path: '/relatorios', icon: 'relatorios', enabled: true }
      ]
    },
    {
      titleKey: 'nav.section.gestao',
      items: [
        { labelKey: 'nav.item.dashboard', path: '/dashboard', icon: 'dashboard', enabled: true },
        { labelKey: 'nav.item.templates', path: '/templates', icon: 'templates', enabled: true },
        { labelKey: 'nav.item.mensagens', path: '/mensagens', icon: 'mensagens', enabled: true },
        { labelKey: 'nav.item.pendencias', path: '/pendencias', icon: 'pending', enabled: true },
        { labelKey: 'nav.item.agenda', path: '/agenda', icon: 'agenda', enabled: true },
        { labelKey: 'nav.item.crmLeads', path: '/crm-leads', icon: 'clients', enabled: true },
        { labelKey: 'nav.item.configuracoes', path: '/configuracoes', icon: 'settings', enabled: true }
      ]
    }
  ];
}

let brandTextElement: HTMLElement | null = null;

export function refreshSidebarBrand(): void { if (brandTextElement) {
  brandTextElement.textContent = getSettings().companyName || 'HUB';
  brandTextElement.title = brandTextElement.textContent ?? '';
} }

export function createSidebar(): HTMLElement {
  const sidebar = createElement('aside', { className: 'sidebar' });
  const brand = createElement('div', { className: 'sidebar-brand' });
  const brandMark = createLogoMark('sidebar-mark');
  brandTextElement = createElement('span', { textContent: getSettings().companyName || 'HUB' });
  brandTextElement.title = brandTextElement.textContent ?? '';
  const nav = createElement('nav', { className: 'sidebar-nav' });

  brand.append(brandMark, brandTextElement);

  const visibleSections = buildSections().map((section) => ({ ...section, items: [...section.items] }));
  const administrationItems: SidebarLink[] = [
    { labelKey: 'nav.item.usuarios', path: '/usuarios', icon: 'clients', enabled: true }
  ];
  if (getCurrentUser()?.isPlatformAdmin && !getCurrentUser()?.platformViewEmpresaId) {
    administrationItems.push({ labelKey: 'nav.item.platform', path: '/platform', icon: 'dashboard', enabled: true });
    administrationItems.push({ labelKey: 'nav.item.funcionarios', path: '/platform/funcionarios', icon: 'clients', enabled: true });
  }
  visibleSections.push({ titleKey: 'nav.section.administracao', items: administrationItems });

  visibleSections.forEach((section) => {
    const sectionElement = createElement('div', { className: 'sidebar-section' });

    if (section.titleKey) {
      sectionElement.appendChild(createElement('span', {
        className: 'sidebar-section-title',
        textContent: t(section.titleKey)
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
  const itemLabel = t(item.labelKey);
  const label = createElement('span', { textContent: itemLabel });

  if (!item.enabled) {
    const disabledLink = createElement('span', { className: 'sidebar-link disabled' });
    disabledLink.title = t('nav.comingSoon');
    disabledLink.append(icon, label);
    return disabledLink;
  }

  const isActive = item.path === window.location.pathname
    || (item.path === '/regras-cobranca' && window.location.pathname.startsWith('/regras-cobranca/'))
    || (window.location.pathname === '/' && item.path === '/dashboard');
  const link = createElement('a', { className: isActive ? 'sidebar-link active' : 'sidebar-link' });

  link.href = item.path;
  link.title = itemLabel;
  link.setAttribute('aria-label', itemLabel);
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
  card.title = `${user?.nome || user?.email || 'Usuário'} — ${user?.empresaNome || roleLabel(user?.role)}`;
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
  if (user?.platformViewEmpresaId) {
    text.appendChild(createElement('span', {
      className: 'sidebar-user-role',
      textContent: `${t('nav.viewing')}: ${user.platformViewEmpresaNome ?? '—'}`
    }));
  }
  card.append(avatar, text);
  return card;
}

function createVersionTag(): HTMLElement {
  return createElement('span', { className: 'sidebar-version', textContent: `HUB ${HUB_VERSION}` });
}

function createLogoutButton(): HTMLElement {
  const logoutButton = createElement('button', {
    className: 'sidebar-logout',
    type: 'button'
  });
  logoutButton.title = t('nav.logout');
  logoutButton.setAttribute('aria-label', t('nav.logout'));
  logoutButton.append(createIcon('login'), createElement('span', {
    className: 'sidebar-logout-label', textContent: t('nav.logout')
  }));

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
  const keys: Record<string, string> = {
    owner: 'nav.role.owner',
    admin: 'nav.role.admin',
    operator: 'nav.role.operator',
    financial: 'nav.role.financial',
    viewer: 'nav.role.viewer'
  };
  return (role && keys[role] && t(keys[role])) || role || t('nav.role.default');
}
