export function createElement<K extends keyof HTMLElementTagNameMap>(
  tagName: K,
  options: {
    className?: string;
    textContent?: string;
    type?: HTMLButtonElement['type'];
  } = {}
): HTMLElementTagNameMap[K] {
  const element = document.createElement(tagName);

  if (options.className) element.className = options.className;
  if (options.textContent) element.textContent = options.textContent;
  if (options.type && element instanceof HTMLButtonElement) element.type = options.type;

  return element;
}

export function emptyState(message: string, small = false): HTMLLIElement {
  return createElement('li', {
    className: small ? 'empty-state small' : 'empty-state',
    textContent: message
  });
}

// Compartilhado entre DataTable (dot de status) e ClientDetailView (badge de status) --
// mesma regra de negocio, um lugar so pra decidir o que e "sucesso" vs "atencao".
export function statusTone(status: string): 'success' | 'warning' {
  const normalized = status
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '');

  return normalized.includes('concluido') || normalized.includes('online') ? 'success' : 'warning';
}