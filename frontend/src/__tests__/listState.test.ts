import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createDebouncedInput, matchesListSearch, pageSlice, readListParam, readPositiveListParam, writeListState } from '../services/listState';

describe('listState', () => {
  beforeEach(() => { window.history.replaceState({}, '', '/ucs'); });

  it('escreve e le estado da lista na URL, removendo valores vazios', () => {
    writeListState({ busca: 'joao', pagina: 2, filtro: null, ativo: false }, 'replace');
    expect(window.location.search).toBe('?busca=joao&pagina=2');
    expect(readListParam('busca')).toBe('joao');
    expect(readPositiveListParam('pagina')).toBe(2);
    writeListState({ busca: '' }, 'replace');
    expect(readListParam('busca')).toBeUndefined();
  });

  it('pagina invalida cai no fallback', () => {
    writeListState({ pagina: '-3' }, 'replace');
    expect(readPositiveListParam('pagina')).toBe(1);
    writeListState({ pagina: 'abc' }, 'replace');
    expect(readPositiveListParam('pagina', 7)).toBe(7);
  });

  it('busca ignora acentos e caixa', () => {
    expect(matchesListSearch('joao', 'João da Silva')).toBe(true);
    expect(matchesListSearch('SILVA', 'João da Silva')).toBe(true);
    expect(matchesListSearch('maria', 'João da Silva')).toBe(false);
    expect(matchesListSearch('', 'qualquer')).toBe(true);
  });

  it('pageSlice limita a pagina ao intervalo valido', () => {
    const rows = Array.from({ length: 23 }, (_, i) => i);
    expect(pageSlice(rows, 1, 10)).toEqual({ rows: rows.slice(0, 10), page: 1, pages: 3 });
    expect(pageSlice(rows, 9, 10)).toEqual({ rows: rows.slice(20), page: 3, pages: 3 });
    expect(pageSlice([], 5, 10)).toEqual({ rows: [], page: 1, pages: 1 });
  });

  it('debounce dispara uma vez com o ultimo valor, sem espacos', () => {
    vi.useFakeTimers();
    const spy = vi.fn();
    const apply = createDebouncedInput(spy, 300);
    apply('a'); apply('ab'); apply(' abc ');
    vi.advanceTimersByTime(299);
    expect(spy).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(spy).toHaveBeenCalledTimes(1);
    expect(spy).toHaveBeenCalledWith('abc');
    vi.useRealTimers();
  });
});
