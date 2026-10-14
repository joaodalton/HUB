import { describe, expect, it } from 'vitest';
import { cnpjError, cpfError, phoneError, ucError } from '../components/cadastroFields';

describe('cpfError', () => {
  it('aceita CPF valido com e sem mascara', () => {
    expect(cpfError('529.982.247-25')).toBe('');
    expect(cpfError('52998224725')).toBe('');
  });
  it('rejeita digito verificador errado, sequencia repetida e tamanho errado', () => {
    expect(cpfError('529.982.247-26')).not.toBe('');
    expect(cpfError('111.111.111-11')).not.toBe('');
    expect(cpfError('1234567890')).not.toBe('');
    expect(cpfError('abc')).not.toBe('');
  });
});

describe('cnpjError', () => {
  it('aceita CNPJ valido', () => {
    expect(cnpjError('11.222.333/0001-81')).toBe('');
  });
  it('rejeita CNPJ invalido', () => {
    expect(cnpjError('11.222.333/0001-82')).not.toBe('');
    expect(cnpjError('00.000.000/0000-00')).not.toBe('');
  });
});

describe('ucError', () => {
  it('so valida Copel: 12 ou 15 digitos', () => {
    expect(ucError('123456789012', 'Copel')).toBe('');
    expect(ucError('123456789012345', 'COPEL')).toBe('');
    expect(ucError('1234567', 'copel')).not.toBe('');
    expect(ucError('qualquer-coisa', 'CPFL')).toBe('');
  });
});

describe('phoneError', () => {
  it('aceita celular com 9 digitos e fixo com 8, DDD >= 11', () => {
    expect(phoneError('(19) 99999-8888')).toBe('');
    expect(phoneError('19 3333-4444')).toBe('');
    expect(phoneError('(01) 99999-8888')).not.toBe('');
    expect(phoneError('19 8888-777')).not.toBe('');
  });
});
