export type ListUrlValue = string | number | boolean | null | undefined;

export function readListParam(name: string): string | undefined {
  const value = new URLSearchParams(window.location.search).get(name);
  return value?.trim() || undefined;
}

export function readPositiveListParam(name: string, fallback = 1): number {
  const value = Number(readListParam(name));
  return Number.isSafeInteger(value) && value > 0 ? value : fallback;
}

/** Keeps list context shareable without triggering a route reload for each control change. */
export function writeListState(values: Record<string, ListUrlValue>, mode: 'push' | 'replace' = 'push'): void {
  const url = new URL(window.location.href);
  Object.entries(values).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '' || value === false) url.searchParams.delete(key);
    else url.searchParams.set(key, String(value));
  });
  const next = `${url.pathname}${url.search}`;
  window.history[mode === 'push' ? 'pushState' : 'replaceState']({}, '', next);
}

export function createDebouncedInput(callback: (value: string) => void, delay = 300): (value: string) => void {
  let timer: number | undefined;
  return (value: string) => {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => callback(value.trim()), delay);
  };
}

export function matchesListSearch(query: string, value: string): boolean {
  if (!query) return true;
  const normalize = (input: string) => input.toLocaleLowerCase('pt-BR').normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  return normalize(value).includes(normalize(query));
}

export function pageSlice<T>(rows: T[], page: number, pageSize: number): { rows: T[]; page: number; pages: number } {
  const pages = Math.max(1, Math.ceil(rows.length / pageSize));
  const safePage = Math.min(Math.max(page, 1), pages);
  return { rows: rows.slice((safePage - 1) * pageSize, safePage * pageSize), page: safePage, pages };
}
