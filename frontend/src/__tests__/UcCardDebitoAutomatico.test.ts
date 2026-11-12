import { describe, expect, it, vi } from 'vitest';
import { createUcCard } from '../components/UcCard';

const base = { id: 1, clienteId: 1, clienteNome: 'F', codigo: '123', apelido: '', documento: null, endereco: null, cep: null,
  concessionaria: 'Outra', geracaoPropria: false, diaEmissaoFatura: null, consumo: null, baseTarifaria: 'B1', desconto: '',
  tipoLigacao: 'Monofasico' as const, inicioContrato: null, terminoContrato: null, carenciaMeses: null,
  percentualDescontoCarencia: null, conexoes: [] };
const clients = [{ id: 1, nome: 'F', concessionaria: 'Outra' }] as never;

function checkbox(root: HTMLElement): HTMLInputElement {
  const label = Array.from(root.querySelectorAll('label')).find((l) => l.textContent?.includes('Débito automático na concessionária'));
  return label!.querySelector('input') as HTMLInputElement;
}

describe('UcCard debitoAutomatico', () => {
  it('loads the current value, shows help and sends a real boolean', () => {
    const onSave = vi.fn();
    const card = createUcCard({ uc: { ...base, debitoAutomatico: true }, clients, availablePlants: [], onSave, onCancel: vi.fn() });
    expect(card.textContent).toContain('Marcada: o boleto do HUB não inclui o valor da fatura da concessionária (cobrança separada).');
    expect(checkbox(card).checked).toBe(true);
    card.querySelector('form')!.dispatchEvent(new Event('submit', { cancelable: true }));
    expect(onSave.mock.calls[0][0].debitoAutomatico).toBe(true);
  });

  it('defaults to false and follows the checkbox', () => {
    const onSave = vi.fn();
    const card = createUcCard({ uc: { ...base }, clients, availablePlants: [], onSave, onCancel: vi.fn() });
    const input = checkbox(card);
    expect(input.checked).toBe(false);
    input.checked = true;
    card.querySelector('form')!.dispatchEvent(new Event('submit', { cancelable: true }));
    expect(onSave.mock.calls[0][0].debitoAutomatico).toBe(true);
  });
});
