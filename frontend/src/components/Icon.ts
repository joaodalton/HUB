// frontend/src/components/Icon.ts
// Set central de icones SVG (stroke=currentColor, sem cor/tamanho fixo --
// herda do elemento pai via CSS). Nao duplicar SVG solto em outro componente,
// importar daqui. Tamanho e cor sao definidos por CSS no contexto de uso
// (ex.: .sidebar-icon, .icon-button .icon), nao aqui.
import { createElement } from '../dom';

export type IconName =
  | 'documents'
  | 'clients'
  | 'ucs'
  | 'plants'
  | 'pending'
  | 'agenda'
  | 'settings'
  | 'upload'
  | 'x'
  | 'more'
  | 'edit'
  | 'trash'
  | 'plus'
  | 'eye'
  | 'dashboard'
  | 'rateio'
  | 'faturas'
  | 'pagamentos'
  | 'cobrancas'
  | 'templates'
  | 'mensagens'
  | 'integracoes'
  | 'permissoes'
  | 'check'
  | 'user'
  | 'lock'
  | 'login';

const paths: Record<IconName, string> = {
  documents: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>',
  clients: '<circle cx="8.5" cy="8" r="3"/><path d="M2.5 19c0-3.3 2.7-6 6-6s6 2.7 6 6"/><circle cx="16.5" cy="8.5" r="2.5"/><path d="M15 12.2c2.6.4 4.5 2.6 4.5 5.3"/>',
  ucs: '<path d="M9 2v6M15 2v6"/><path d="M6 8h12v4a6 6 0 0 1-12 0z"/><path d="M12 18v4"/>',
  plants: '<circle cx="12" cy="12" r="4"/><path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1"/>',
  pending: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
  agenda: '<rect x="3.5" y="4.5" width="17" height="16" rx="2"/><path d="M3.5 9.5h17M8 3v3M16 3v3"/>',
  settings: '<path d="M4 6h9M17 6h3"/><circle cx="14" cy="6" r="2"/><path d="M4 12h3M11 12h9"/><circle cx="8" cy="12" r="2"/><path d="M4 18h9M17 18h3"/><circle cx="14" cy="18" r="2"/>',
  upload: '<path d="M12 16V4"/><path d="M7 9l5-5 5 5"/><path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3"/>',
  x: '<path d="M6 6l12 12M18 6 6 18"/>',
  more: '<circle cx="12" cy="5" r="1.4"/><circle cx="12" cy="12" r="1.4"/><circle cx="12" cy="19" r="1.4"/>',
  edit: '<path d="M4 20h4l10.5-10.5a2 2 0 0 0 0-2.8l-1.2-1.2a2 2 0 0 0-2.8 0L4 17v3z"/><path d="M13 5.5 18.5 11"/>',
  trash: '<path d="M4 7h16"/><path d="M9 7V4.5A1.5 1.5 0 0 1 10.5 3h3A1.5 1.5 0 0 1 15 4.5V7"/><path d="M6 7l1 13a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-13"/><path d="M10 11v6M14 11v6"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  eye: '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="2.6"/>',
  dashboard: '<rect x="3" y="3" width="8" height="8" rx="1.5"/><rect x="13" y="3" width="8" height="8" rx="1.5"/><rect x="3" y="13" width="8" height="8" rx="1.5"/><rect x="13" y="13" width="8" height="8" rx="1.5"/>',
  rateio: '<circle cx="7" cy="7" r="2.2"/><circle cx="17" cy="17" r="2.2"/><path d="M18 6 6 18"/>',
  faturas: '<path d="M6 3h9l3 3v15l-2-1-2 1-2-1-2 1-2-1-2 1V3z"/><path d="M8 8h6M8 12h6M8 16h4"/>',
  pagamentos: '<rect x="2.5" y="5.5" width="19" height="13" rx="2"/><path d="M2.5 10h19"/><path d="M6 15h4"/>',
  cobrancas: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5v5.5"/><path d="M12 16.2v.1"/>',
  templates: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 9v12"/>',
  mensagens: '<path d="M4 5.5h16a1 1 0 0 1 1 1V15a1 IconName 0 0 1-1 1H9l-4.5 4V16H4a1 1 0 0 1-1-1V6.5a1 1 0 0 1 1-1z"/>',
  integracoes: '<path d="M9 15 15 9"/><path d="M7 12.5 5.5 14a3 3 0 0 0 4.2 4.2L11 17"/><path d="M17 11.5 18.5 10a3 3 0 0 0-4.2-4.2L13 7"/>',
  permissoes: '<path d="M12 3.5 19 6v6c0 4.5-3 7.5-7 8.5-4-1-7-4-7-8.5V6z"/><path d="M9.5 12l1.8 1.8L14.5 10"/>',
  check: '<path d="M5 12.5 9.5 17 19 7.5"/>',
  user: '<circle cx="12" cy="8" r="3.5"/><path d="M5 20c0-3.9 3.1-7 7-7s7 3.1 7 7"/>',
  lock: '<rect x="5" y="10" width="14" height="10" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
  login: '<path d="M13 4h4a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-4"/><path d="M3 12h13"/><path d="M12 7l5 5-5 5"/>'
};

function markup(name: IconName): string {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${paths[name]}</svg>`;
}

// className default 'icon' -- tamanho e definido por CSS contextual
// (ver .icon em shared.css + overrides em cada dominio que usar).
export function createIcon(name: IconName, className = 'icon'): HTMLSpanElement {
  const wrapper = createElement('span', { className });
  wrapper.innerHTML = markup(name);
  return wrapper;
}
