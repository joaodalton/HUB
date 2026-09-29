import { createElement } from '../dom';
import { getCurrentUser } from '../services/authService';
import { createIcon, type IconName } from './Icon';

type PaletteAction = { label: string; description: string; path: string; icon: IconName; shortcut?: string; allowed: () => boolean };

const always = (): boolean => true;
const roleIn = (...roles: string[]) => (): boolean => roles.includes(getCurrentUser()?.role ?? '');
const platformAdmin = (): boolean => getCurrentUser()?.isPlatformAdmin === true;

const actions: PaletteAction[] = [
  { label: 'Abrir dashboard', description: 'Visão operacional', path: '/dashboard', icon: 'dashboard', shortcut: '1', allowed: always },
  { label: 'Ver pendências', description: 'Itens que exigem atenção', path: '/pendencias', icon: 'pending', shortcut: '2', allowed: always },
  { label: 'Abrir agenda', description: 'Prazos e compromissos', path: '/agenda', icon: 'agenda', shortcut: '3', allowed: always },
  { label: 'Localizar cliente', description: 'Pesquisar na lista de clientes', path: '/clientes', icon: 'clients', shortcut: '4', allowed: always },
  { label: 'Localizar UC', description: 'Pesquisar na lista de UCs', path: '/ucs', icon: 'ucs', shortcut: '5', allowed: always },
  { label: 'Localizar usina', description: 'Pesquisar na lista de usinas', path: '/usinas', icon: 'plants', shortcut: '6', allowed: always },
  { label: 'Abrir documentos', description: 'Consultar arquivos existentes', path: '/documentos', icon: 'documents', shortcut: '7', allowed: always },
  { label: 'Abrir faturas', description: 'Operação financeira', path: '/faturas', icon: 'faturas', shortcut: '8', allowed: roleIn('owner', 'admin', 'financial') },
  { label: 'Regras de cobrança', description: 'Configuração financeira', path: '/regras-cobranca', icon: 'cobrancas', shortcut: '9', allowed: roleIn('owner', 'admin', 'financial') },
  { label: 'Gerenciar usuários', description: 'Acessos da empresa', path: '/usuarios', icon: 'user', allowed: roleIn('owner', 'admin') },
  { label: 'Abrir configurações', description: 'Preferências e integrações', path: '/configuracoes', icon: 'settings', allowed: roleIn('owner', 'admin') },
  { label: 'Gerenciar empresas', description: 'Administração da plataforma', path: '/empresas', icon: 'clients', allowed: platformAdmin }
];

export function createCommandPalette(): { element: HTMLElement; trigger: HTMLButtonElement } {
  const trigger = createElement('button', { className: 'command-palette-trigger secondary-button', type: 'button' });
  trigger.append(createIcon('dashboard'), document.createTextNode('Ações rápidas'), createElement('kbd', { textContent: navigator.platform.includes('Mac') ? '⌘ K' : 'Ctrl K' }));
  trigger.title = 'Abrir ações rápidas';
  trigger.setAttribute('aria-keyshortcuts', 'Control+K Meta+K');

  const overlay = createElement('div', { className: 'command-palette-overlay' });
  overlay.hidden = true;
  const dialog = createElement('section', { className: 'command-palette' });
  dialog.setAttribute('role', 'dialog'); dialog.setAttribute('aria-modal', 'true'); dialog.setAttribute('aria-label', 'Ações rápidas');
  const input = createElement('input'); input.type = 'search'; input.placeholder = 'Digite uma ação ou destino…'; input.setAttribute('aria-label', 'Filtrar ações');
  const list = createElement('div', { className: 'command-palette-list' }); list.setAttribute('role', 'listbox');
  const hint = createElement('p', { className: 'command-palette-hint', textContent: '↑↓ navegar · Enter abrir · Esc fechar · 1–9 abrir destino' });
  dialog.append(input, list, hint); overlay.appendChild(dialog);
  let previousFocus: HTMLElement | null = null;
  let visible: PaletteAction[] = [];
  let activeIndex = 0;

  const navigate = (path: string): void => { close(); window.history.pushState({}, '', path); window.dispatchEvent(new PopStateEvent('popstate')); };
  const render = (): void => {
    const query = normalize(input.value);
    visible = actions.filter(action => action.allowed() && normalize(`${action.label} ${action.description}`).includes(query));
    activeIndex = Math.min(activeIndex, Math.max(0, visible.length - 1));
    list.replaceChildren();
    if (!visible.length) { list.appendChild(createElement('p', { className: 'command-palette-empty', textContent: 'Nenhuma ação disponível.' })); return; }
    visible.forEach((action, index) => {
      const button = createElement('button', { className: index === activeIndex ? 'command-palette-item active' : 'command-palette-item', type: 'button' });
      button.setAttribute('role', 'option'); button.setAttribute('aria-selected', String(index === activeIndex));
      const text = createElement('span', { className: 'command-palette-item-text', innerHTML: `<strong>${escapeHtml(action.label)}</strong><small>${escapeHtml(action.description)}</small>` });
      button.append(createIcon(action.icon), text);
      if (action.shortcut) {
        const shortcut = createElement('kbd', { className: 'command-palette-item-shortcut', textContent: action.shortcut });
        shortcut.setAttribute('aria-label', `Atalho ${action.shortcut}`);
        button.appendChild(shortcut);
      }
      button.addEventListener('mouseenter', () => { activeIndex = index; render(); });
      button.addEventListener('click', () => navigate(action.path));
      list.appendChild(button);
    });
  };
  const open = (): void => { previousFocus = document.activeElement as HTMLElement | null; overlay.hidden = false; input.value = ''; activeIndex = 0; render(); queueMicrotask(() => input.focus()); };
  const close = (): void => { if (overlay.hidden) return; overlay.hidden = true; previousFocus?.focus(); };
  trigger.addEventListener('click', open);
  overlay.addEventListener('mousedown', event => { if (event.target === overlay) close(); });
  overlay.addEventListener('keydown', event => {
    if (event.key === 'Escape') { event.preventDefault(); close(); }
    if ((event.key === 'ArrowDown' || event.key === 'ArrowUp') && visible.length) { event.preventDefault(); activeIndex = (activeIndex + (event.key === 'ArrowDown' ? 1 : visible.length - 1)) % visible.length; render(); input.focus(); }
    if (event.key === 'Enter' && visible[activeIndex]) { event.preventDefault(); navigate(visible[activeIndex].path); }
    const shortcutAction = !isEditableTarget(event.target) && !event.ctrlKey && !event.metaKey && !event.altKey && !event.shiftKey
      ? visible.find(action => action.shortcut === event.key)
      : undefined;
    if (shortcutAction) { event.preventDefault(); navigate(shortcutAction.path); }
    if (event.key === 'Tab') { const focusable = [input, ...list.querySelectorAll<HTMLButtonElement>('button')]; const first = focusable[0]; const last = focusable[focusable.length - 1]; if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); } else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); } }
  });
  input.addEventListener('input', () => { activeIndex = 0; render(); });
  const shortcut = (event: KeyboardEvent): void => { if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); overlay.hidden ? open() : close(); } };
  window.addEventListener('keydown', shortcut);
  const observer = new MutationObserver(() => { if (!overlay.isConnected) { window.removeEventListener('keydown', shortcut); observer.disconnect(); } });
  observer.observe(document.body, { childList: true, subtree: true });
  return { element: overlay, trigger };
}

function normalize(value: string): string { return value.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, ''); }
function escapeHtml(value: string): string { const node = document.createElement('span'); node.textContent = value; return node.innerHTML; }
function isEditableTarget(target: EventTarget | null): boolean {
  return target instanceof HTMLInputElement
    || target instanceof HTMLTextAreaElement
    || target instanceof HTMLSelectElement
    || (target instanceof HTMLElement && target.isContentEditable);
}
