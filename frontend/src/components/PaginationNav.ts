import { createElement } from '../dom';

export type PaginationState = { page: number; pageSize: number; total: number; pages: number };

// Mesmo padrao visual/comportamental de FaturasPage.ts (createPagination) --
// extraido aqui pra ser reaproveitado pelas outras listagens com paginacao
// server-side (Clientes, UCs, Usinas, Pendencias, Usuarios, Documentos).
export function createPaginationNav(
  pagination: PaginationState,
  busy: boolean,
  onChange: (page: number) => void,
  ariaLabel = 'Páginas'
): HTMLElement {
  const nav = createElement('nav', { className: 'list-pagination' });
  nav.setAttribute('aria-label', ariaLabel);

  const previous = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Anterior' });
  previous.disabled = busy || pagination.page <= 1;
  previous.addEventListener('click', () => onChange(pagination.page - 1));

  const next = createElement('button', { className: 'secondary-button', type: 'button', textContent: 'Próxima' });
  next.disabled = busy || pagination.page >= pagination.pages;
  next.addEventListener('click', () => onChange(pagination.page + 1));

  nav.append(
    previous,
    createElement('span', { textContent: `${pagination.pages ? pagination.page : 0} de ${pagination.pages}` }),
    next
  );
  return nav;
}
