import { createElement } from '../dom';

export const digits = (value: string): string => value.replace(/\D/g, '');
export const phoneDigits = (value: string): string => {
  const raw = value.trim();
  const number = digits(raw);
  return raw.startsWith('+55') ? number.slice(2) : number;
};

export function validateField(input: HTMLInputElement, message: string): boolean {
  let error = input.parentElement?.querySelector<HTMLElement>('.form-field-error');
  if (!error) {
    error = createElement('small', { className: 'form-field-error' });
    input.after(error);
  }
  input.setCustomValidity(message);
  error.textContent = message;
  input.setAttribute('aria-invalid', String(Boolean(message)));
  if (message) input.reportValidity();
  return !message;
}

export function phoneError(value: string): string {
  if (!/^\+?[\d\s().-]+$/.test(value.trim())) return 'Informe um telefone válido.';
  const number = phoneDigits(value);
  return (/^\d{2}9\d{8}$/.test(number) || /^\d{10}$/.test(number)) && Number(number.slice(0, 2)) >= 11
    ? '' : 'Informe DDD e celular de 9 dígitos ou telefone fixo de 8 dígitos.';
}

export function cpfError(value: string): string {
  if (!/^[\d.\s-]+$/.test(value.trim())) return 'Informe um CPF válido com 11 dígitos.';
  const number = digits(value);
  if (number.length !== 11 || /^(\d)\1+$/.test(number)) return 'Informe um CPF válido com 11 dígitos.';
  for (let size = 9; size <= 10; size++) {
    const sum = [...number.slice(0, size)].reduce((total, digit, index) => total + Number(digit) * (size + 1 - index), 0);
    if (Number(number[size]) !== ((sum * 10) % 11) % 10) return 'Informe um CPF válido com 11 dígitos.';
  }
  return '';
}

export function cnpjError(value: string): string {
  if (!/^[\d.\s/-]+$/.test(value.trim())) return 'Informe um CNPJ válido com 14 dígitos.';
  const number = digits(value);
  if (number.length !== 14 || /^(\d)\1+$/.test(number)) return 'Informe um CNPJ válido com 14 dígitos.';
  for (let size = 12; size <= 13; size++) {
    const weights = size === 12 ? [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2] : [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
    const sum = weights.reduce((total, weight, index) => total + Number(number[index]) * weight, 0);
    if (Number(number[size]) !== (sum % 11 < 2 ? 0 : 11 - sum % 11)) return 'Informe um CNPJ válido com 14 dígitos.';
  }
  return '';
}

export function ucError(value: string, concessionaria: string): string {
  if (concessionaria.trim().toLowerCase() !== 'copel') return '';
  return /^(?:\d{12}|\d{15})$/.test(value) ? '' : 'UC Copel deve ter 12 ou 15 dígitos.';
}
