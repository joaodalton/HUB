import { describe, expect, it } from 'vitest';
import { responsavelLabel, type PendenciaRow } from '../services/pendenciasService';

const base: PendenciaRow = {
  id: 1, tipo: 'pendencia', categoria: 'Financeiro', origem: 'Manual',
  titulo: 'Revisar contrato', descricao: null, clienteId: null, clienteNome: null,
  ucId: null, ucCodigo: null, usinaId: null, usinaNome: null, documentoId: null, documentoNome: null,
  faturaId: null, prazo: null, prioridade: 'media', responsavelTipo: 'usuario',
  responsavelId: null, responsavelNome: null, responsavelCargo: null,
  status: 'aberta', metadados: null, criadoEm: '2026-01-01T00:00:00', atualizadoEm: null,
  resolvidoEm: null, comentarios: []
};

describe('responsavelLabel', () => {
  it('returns the user name when responsavelTipo is usuario', () => {
    expect(responsavelLabel({ ...base, responsavelTipo: 'usuario', responsavelNome: 'Maria' })).toBe('Maria');
  });

  it('returns "Cargo: <label>" when responsavelTipo is cargo', () => {
    expect(responsavelLabel({ ...base, responsavelTipo: 'cargo', responsavelCargo: 'admin' })).toBe('Cargo: Administrador');
  });

  it('returns "-" when there is no responsavel', () => {
    expect(responsavelLabel({ ...base, responsavelTipo: 'usuario', responsavelNome: null })).toBe('-');
  });
});
