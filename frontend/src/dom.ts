// frontend/src/dom.ts
// helpers para criação de elementos DOM no frontend do HUB.
// createElement é genérico: aceita qualquer tag HTML e um registro de
// atributos/opções. Para input com type checkbox/password/date/etc. usa-se
// createElementRaw (que não faz validação de tipo).

export function createElement<K extends keyof HTMLElementTagNameMap>(
  tagName: K,
  options?: {
    className?: string;
    textContent?: string;
    innerHTML?: string;
    type?: string;
    title?: string;
    checked?: boolean;
    htmlFor?: string;
    for?: string;
    name?: string;
    placeholder?: string;
    required?: boolean;
    min?: string;
    max?: string;
    'data-testid'?: string;
    accept?: string;
    multiple?: boolean;
    readonly?: boolean;
    disabled?: boolean;
    value?: string;
  }
): HTMLElementTagNameMap[K] {
  const element = document.createElement(tagName) as HTMLElementTagNameMap[K];

  if (options?.className) element.className = options.className;
  if (options?.textContent != null) element.textContent = options.textContent;
  if (options?.innerHTML) element.innerHTML = options.innerHTML;
  if (options?.type != null) element.setAttribute('type', options.type);
  if (options?.title != null) element.title = options.title;
  if (options?.checked != null) (element as HTMLInputElement).checked = options.checked;
  if (options?.htmlFor != null) element.setAttribute('for', options.htmlFor);
  if (options?.for != null) element.setAttribute('for', options.for);
  if (options?.name != null) (element as HTMLInputElement).name = options.name;
  if (options?.placeholder != null) (element as HTMLInputElement).placeholder = options.placeholder;
  if (options?.required != null) (element as HTMLInputElement).required = options.required;
  if (options?.min != null) (element as HTMLInputElement).min = options.min;
  if (options?.max != null) (element as HTMLInputElement).max = options.max;
  if (options?.['data-testid'] != null) element.setAttribute('data-testid', options['data-testid']);
  if (options?.accept != null) (element as HTMLInputElement).accept = options.accept;
  if (options?.multiple != null) (element as HTMLInputElement).multiple = options.multiple;
  if (options?.readonly != null) (element as HTMLInputElement).readOnly = options.readonly;
  if (options?.disabled != null) (element as HTMLInputElement).disabled = options.disabled;
  if (options?.value != null) (element as HTMLInputElement).value = options.value;

  return element;
}

export function createElementRaw(tagName: string): HTMLElement {
  return document.createElement(tagName);
}

// Compartilhado entre DataTable (dot de status) e ClientDetailView (badge de status) --
// mesma regra de negocio, um lugar so pra decidir o que e "sucesso" vs "atencao".
export function statusTone(status: string): 'success' | 'warning' {
  const normalized = status
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\\u0300-\\u036f]/g, '');

  return normalized.includes('concluido') || normalized.includes('online') ? 'success' : 'warning';
}

export function emptyState(message: string, small = false): HTMLLIElement {
  return createElement('li', {
    className: small ? 'empty-state small' : 'empty-state',
    textContent: message
  });
}
