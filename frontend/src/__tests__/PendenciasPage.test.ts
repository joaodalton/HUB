import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// Covers the three split pendencias modules (PendenciasListView,
// PendenciasDetailPanel, PendenciasEditorModal) through the page that wires
// them together -- same integration level the modules were split from.

vi.mock('../layouts/BaseLayout', () => ({
  createBaseLayout: ({ content }: { content: HTMLElement }) => content,
}));

vi.mock('../services/clientsService', () => ({ getClients: vi.fn() }));
vi.mock('../services/ucsService', () => ({ getUcs: vi.fn() }));
vi.mock('../services/plantService', () => ({ getPlants: vi.fn() }));
vi.mock('../services/userService', () => ({ getUsers: vi.fn() }));
vi.mock('../services/pendenciaCategoriasService', () => ({
  getExtraCategorias: vi.fn(),
  addExtraCategoria: vi.fn(),
}));
vi.mock('../services/logsService', () => ({ getEntityLogs: vi.fn() }));

vi.mock('../services/pendenciasService', async () => {
  const actual = await vi.importActual<typeof import('../services/pendenciasService')>('../services/pendenciasService');
  return {
    ...actual,
    getPendencias: vi.fn(),
    getPendenciaResumo: vi.fn(),
    verificarPendencias: vi.fn(),
    createPendencia: vi.fn(),
    updatePendencia: vi.fn(),
    deletePendencia: vi.fn(),
    resolverPendencia: vi.fn(),
    cancelarPendencia: vi.fn(),
    reabrirPendencia: vi.fn(),
    addComentario: vi.fn(),
  };
});

import {
  getPendencias, getPendenciaResumo, verificarPendencias, createPendencia, updatePendencia
} from '../services/pendenciasService';
import { getClients } from '../services/clientsService';
import { getUcs } from '../services/ucsService';
import { getPlants } from '../services/plantService';
import { getUsers } from '../services/userService';
import { getExtraCategorias } from '../services/pendenciaCategoriasService';
import { getEntityLogs } from '../services/logsService';
import { createPendenciasPage } from '../pages/PendenciasPage';

async function flush(): Promise<void> {
  await Promise.resolve(); await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
}

const resumo = { pendencias: 1, alertas: 0, erros: 0 };

const pendencia = {
  id: 1, tipo: 'pendencia' as const, categoria: 'Financeiro', origem: 'Manual',
  titulo: 'Revisar contrato', descricao: 'Falta assinatura.', clienteId: null, clienteNome: null,
  ucId: null, ucCodigo: null, usinaId: null, usinaNome: null, documentoId: null, documentoNome: null,
  faturaId: null, prazo: null, prioridade: 'media' as const, responsavelTipo: 'usuario' as const,
  responsavelId: null, responsavelNome: null, responsavelCargo: null,
  status: 'aberta' as const, metadados: null, criadoEm: '2026-01-01T00:00:00', atualizadoEm: null,
  resolvidoEm: null, comentarios: []
};

describe('PendenciasPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.history.replaceState({}, '', '/');
    vi.mocked(getClients).mockResolvedValue([]);
    vi.mocked(getUcs).mockResolvedValue([]);
    vi.mocked(getPlants).mockResolvedValue([]);
    vi.mocked(getUsers).mockResolvedValue([]);
    vi.mocked(getExtraCategorias).mockResolvedValue([]);
    vi.mocked(getEntityLogs).mockResolvedValue([]);
    vi.mocked(verificarPendencias).mockResolvedValue({ verificacoes: { ucs_sem_usina: 0, clientes_sem_uc: 0, campos_faltando: 0, documentos_faltando: 0 }, resolvidas: 0, total_criadas: 0 });
  });
  afterEach(() => { vi.restoreAllMocks(); });

  it('renders one row per pendencia when ready (PendenciasListView)', async () => {
    vi.mocked(getPendencias).mockResolvedValue([pendencia]);
    vi.mocked(getPendenciaResumo).mockResolvedValue(resumo);
    const content = createPendenciasPage();
    await flush();
    expect(getPendencias).toHaveBeenCalled();
    expect(content.textContent).toContain('Revisar contrato');
  });

  it('shows the empty state when there are no open pendencias', async () => {
    vi.mocked(getPendencias).mockResolvedValue([]);
    vi.mocked(getPendenciaResumo).mockResolvedValue({ pendencias: 0, alertas: 0, erros: 0 });
    const content = createPendenciasPage();
    await flush();
    expect(content.textContent).toContain('Nenhuma pendencia aberta');
  });

  it('shows an error state when loading fails', async () => {
    vi.mocked(getPendencias).mockRejectedValue(new Error('offline'));
    vi.mocked(getPendenciaResumo).mockRejectedValue(new Error('offline'));
    const content = createPendenciasPage();
    await flush();
    expect(content.textContent).toContain('Nao foi possivel carregar pendencias');
  });

  it('filters by search term (PendenciasListView interaction)', async () => {
    const other = { ...pendencia, id: 2, titulo: 'Outra tarefa' };
    vi.mocked(getPendencias).mockResolvedValue([pendencia, other]);
    vi.mocked(getPendenciaResumo).mockResolvedValue(resumo);
    const content = createPendenciasPage();
    await flush();

    const search = content.querySelector<HTMLInputElement>('input[placeholder="Pesquisar pendências..."]');
    expect(search).toBeInstanceOf(HTMLInputElement);
    search!.value = 'Outra';
    search!.dispatchEvent(new Event('input'));
    await new Promise((resolve) => setTimeout(resolve, 350));
    await flush();

    expect(content.textContent).toContain('Outra tarefa');
    expect(content.textContent).not.toContain('Revisar contrato');
  });

  it('opens the detail panel when a row is clicked (PendenciasDetailPanel)', async () => {
    vi.mocked(getPendencias).mockResolvedValue([pendencia]);
    vi.mocked(getPendenciaResumo).mockResolvedValue(resumo);
    const content = createPendenciasPage();
    await flush();

    const row = content.querySelector('tbody tr');
    expect(row).not.toBeNull();
    row?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flush();

    expect(content.querySelector('.pendencia-detail-panel')).not.toBeNull();
    expect(content.textContent).toContain('Falta assinatura.');
  });

  it('creates a new pendencia from the editor modal (PendenciasEditorModal)', async () => {
    vi.mocked(getPendencias).mockResolvedValue([]);
    vi.mocked(getPendenciaResumo).mockResolvedValue({ pendencias: 0, alertas: 0, erros: 0 });
    vi.mocked(createPendencia).mockResolvedValue(pendencia);
    const content = createPendenciasPage();
    await flush();

    const newButton = Array.from(content.querySelectorAll('button')).find((button) => button.textContent?.includes('Nova Pendência'));
    expect(newButton).toBeInstanceOf(HTMLButtonElement);
    newButton?.click();

    const overlay = document.querySelector('.modal-overlay');
    expect(overlay).not.toBeNull();
    const tituloInput = overlay!.querySelector<HTMLInputElement>('input[type="text"]');
    expect(tituloInput).toBeInstanceOf(HTMLInputElement);
    tituloInput!.value = 'Nova pendência de teste';
    tituloInput!.dispatchEvent(new Event('input'));

    const form = overlay!.querySelector('form');
    form?.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
    await flush();

    expect(createPendencia).toHaveBeenCalledTimes(1);
    expect(vi.mocked(createPendencia).mock.calls[0][0]).toMatchObject({ titulo: 'Nova pendência de teste' });
    overlay?.remove();
  });

  it('sends only responsavelId when tipo stays "usuário" (PendenciasEditorModal)', async () => {
    vi.mocked(getPendencias).mockResolvedValue([]);
    vi.mocked(getPendenciaResumo).mockResolvedValue({ pendencias: 0, alertas: 0, erros: 0 });
    vi.mocked(createPendencia).mockResolvedValue(pendencia);
    const content = createPendenciasPage();
    await flush();

    const newButton = Array.from(content.querySelectorAll('button')).find((button) => button.textContent?.includes('Nova Pendência'));
    newButton?.click();

    const overlay = document.querySelector('.modal-overlay');
    const tituloInput = overlay!.querySelector<HTMLInputElement>('input[type="text"]');
    tituloInput!.value = 'Teste responsável usuário';
    tituloInput!.dispatchEvent(new Event('input'));

    const form = overlay!.querySelector('form');
    form?.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
    await flush();

    const payload = vi.mocked(createPendencia).mock.calls[0][0];
    expect(payload.responsavelTipo).toBe('usuario');
    expect(payload.responsavelCargo).toBeFalsy();
    expect('responsavelId' in payload).toBe(true);
    overlay?.remove();
  });

  it('sends only responsavelCargo when tipo is switched to "cargo" (PendenciasEditorModal)', async () => {
    vi.mocked(getPendencias).mockResolvedValue([]);
    vi.mocked(getPendenciaResumo).mockResolvedValue({ pendencias: 0, alertas: 0, erros: 0 });
    vi.mocked(createPendencia).mockResolvedValue(pendencia);
    const content = createPendenciasPage();
    await flush();

    const newButton = Array.from(content.querySelectorAll('button')).find((button) => button.textContent?.includes('Nova Pendência'));
    newButton?.click();

    const overlay = document.querySelector('.modal-overlay');
    const tituloInput = overlay!.querySelector<HTMLInputElement>('input[type="text"]');
    tituloInput!.value = 'Teste responsável cargo';
    tituloInput!.dispatchEvent(new Event('input'));

    const selects = Array.from(overlay!.querySelectorAll('select'));
    const tipoSelect = selects.find((select) => Array.from(select.options).some((option) => option.value === 'cargo'));
    expect(tipoSelect).toBeInstanceOf(HTMLSelectElement);
    tipoSelect!.value = 'cargo';
    tipoSelect!.dispatchEvent(new Event('change'));

    const form = overlay!.querySelector('form');
    form?.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
    await flush();

    const payload = vi.mocked(createPendencia).mock.calls[0][0];
    expect(payload.responsavelTipo).toBe('cargo');
    expect(payload.responsavelId).toBeFalsy();
    expect(payload.responsavelCargo).toBe('owner');
    overlay?.remove();
  });

  it('pre-selects tipo "cargo" when editing a pendencia with responsavelTipo cargo (PendenciasEditorModal)', async () => {
    const cargoPendencia = { ...pendencia, responsavelTipo: 'cargo' as const, responsavelCargo: 'financial' as const, responsavelId: null };
    vi.mocked(getPendencias).mockResolvedValue([cargoPendencia]);
    vi.mocked(getPendenciaResumo).mockResolvedValue(resumo);
    vi.mocked(updatePendencia).mockResolvedValue(cargoPendencia);
    const content = createPendenciasPage();
    await flush();

    const row = content.querySelector('tbody tr');
    row?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flush();

    const editButton = Array.from(content.querySelectorAll('button')).find((button) => button.textContent?.includes('Editar'));
    editButton?.click();

    const overlay = document.querySelector('.modal-overlay');
    expect(overlay).not.toBeNull();
    const selects = Array.from(overlay!.querySelectorAll('select'));
    const tipoSelect = selects.find((select) => Array.from(select.options).some((option) => option.value === 'cargo'));
    expect(tipoSelect!.value).toBe('cargo');
    const cargoSelect = selects.find((select) => select !== tipoSelect && Array.from(select.options).some((option) => option.value === 'financial'));
    expect(cargoSelect!.value).toBe('financial');
    overlay?.remove();
  });
});
