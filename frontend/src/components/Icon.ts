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
  | 'plus';

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
  plus: '<path d="M12 5v14M5 12h14"/>'
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
