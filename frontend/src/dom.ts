export function createElement<K extends keyof HTMLElementTagNameMap>(
  tagName: K,
  options: {
    className?: string;
    textContent?: string;
    type?: string;
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
