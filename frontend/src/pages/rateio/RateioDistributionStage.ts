import { createElement } from '../../dom';
import { createIcon } from '../../components/Icon';
import type { PlantRow } from '../../services/plantService';
import type { RateioQualificacaoUc, RateioPreview } from '../../services/rateioService';
import { createFunilStat, formatNumber, round2 } from './shared';

type Props = {
  plant: PlantRow;
  ucs: RateioQualificacaoUc[];
  preview: RateioPreview | null;
  selectedUcIds: ReadonlySet<number>;
  overrides: Map<number, number>;
  competencia: string;
  confirming: boolean;
  onBack: () => void;
  onCompetenciaChange: (value: string) => void;
  onApprove: (selecoes: Array<{ ucId: number; percentual: number }>) => void;
  onRemove: (ucId: number) => void;
};

export function renderRateioDistributionStage(props: Props): HTMLElement {
  const { plant, ucs, preview, selectedUcIds, overrides, competencia, confirming, onBack, onCompetenciaChange, onApprove, onRemove } = props;
  const wrapper = createElement('section', { className: 'content-stack' });
  const panel = createElement('section', { className: 'data-panel rateio-distribuicao' });
  const title = createElement('div', { className: 'panel-title' });
  const titleText = createElement('div');
  titleText.append(createElement('span', { className: 'eyebrow', textContent: plant.nome }), createElement('h2', { textContent: 'Proposta de distribuição' }));
  title.appendChild(titleText); panel.appendChild(title);
  const selected = ucs.filter((uc) => selectedUcIds.has(uc.ucId));
  if (!selected.length) {
    panel.appendChild(createElement('p', { className: 'empty-state small', textContent: 'Nenhum cliente selecionado. Volte pra etapa anterior.' }));
    wrapper.appendChild(panel); return wrapper;
  }

  const { list, inputs } = createDistributionList(selected, overrides, onRemove);
  panel.append(createSummary(preview, inputs), list, createCompetenciaField(competencia, onCompetenciaChange));
  const actions = createElement('div', { className: 'form-actions' });
  const back = createElement('button', { className: 'secondary-button', textContent: '← Voltar', type: 'button' });
  const approve = createElement('button', { textContent: confirming ? 'Salvando...' : 'Aprovar proposta', type: 'button' });
  approve.disabled = confirming;
  back.addEventListener('click', onBack);
  approve.addEventListener('click', () => onApprove(inputs.map(({ ucId, input }) => ({ ucId, percentual: Number(input.value) || 0 }))));
  actions.append(back, approve); wrapper.append(panel, actions);
  return wrapper;
}

function createSummary(preview: RateioPreview | null, inputs: Array<{ ucId: number; input: HTMLInputElement }>): HTMLElement {
  const summary = createElement('div', { className: 'rateio-funil-grid' });
  const energy = createFunilStat('Energia distribuída', '—');
  const balance = createFunilStat('Saldo restante', '—');
  const donutStat = createElement('article', { className: 'rateio-distribuicao-summary' });
  const donut = createElement('span', { className: 'rateio-summary-donut' });
  const value = createElement('strong'); donut.appendChild(value);
  const caption = createElement('span', { className: 'rateio-summary-caption' });
  donutStat.append(donut, createElement('span', { className: 'rateio-funil-stat-label', textContent: 'Resumo do rateio' }), caption);
  function refresh(): void {
    const total = inputs.reduce((sum, { input }) => sum + (Number(input.value) || 0), 0);
    const distributed = round2((total / 100) * (preview?.producaoDisponivel ?? 0));
    const remaining = round2((preview?.producaoDisponivel ?? 0) - distributed);
    const energyValue = energy.querySelector('strong');
    const balanceValue = balance.querySelector('strong');
    if (energyValue) energyValue.textContent = `${formatNumber(distributed)} kWh`;
    if (balanceValue) balanceValue.textContent = `${formatNumber(remaining)} kWh`;
    balance.classList.toggle('tone-danger', remaining < 0);
    const displayed = Math.min(Math.max(total, 0), 100);
    donut.style.background = `conic-gradient(var(--accent-secondary) 0 ${displayed}%, var(--panel-deep-soft) ${displayed}% 100%)`;
    value.textContent = `${formatNumber(total)}%`; caption.textContent = `${formatNumber(displayed)}% distribuído`;
  }
  inputs.forEach(({ input }) => input.addEventListener('input', refresh));
  refresh(); summary.append(energy, balance, donutStat); return summary;
}

function createDistributionList(selected: RateioQualificacaoUc[], overrides: Map<number, number>, onRemove: (ucId: number) => void): { list: HTMLElement; inputs: Array<{ ucId: number; input: HTMLInputElement }> } {
  const list = createElement('div', { className: 'rateio-distribuicao-list rateio-distribuicao-list--wizard' });
  const header = createElement('div', { className: 'rateio-distribuicao-row rateio-distribuicao-header' });
  ['Cliente', 'Apelido', 'UC', 'Consumo', '% sugerida', '% real', ''].forEach((label) => header.appendChild(createElement('span', { textContent: label })));
  list.appendChild(header);
  const inputs: Array<{ ucId: number; input: HTMLInputElement }> = [];
  selected.forEach((uc) => {
    const row = createElement('div', { className: 'rateio-distribuicao-row' });
    const input = createElement('input');
    input.type = 'number'; input.min = '0'; input.max = '100'; input.step = '0.01';
    const initial = overrides.get(uc.ucId) ?? uc.percentualSugerido;
    input.value = String(initial); overrides.set(uc.ucId, initial);
    input.addEventListener('input', () => overrides.set(uc.ucId, Number(input.value) || 0));
    inputs.push({ ucId: uc.ucId, input });
    const removeButton = createElement('button', { className: 'icon-button danger', type: 'button', title: 'Remover cliente da distribuição' });
    removeButton.setAttribute('aria-label', 'Remover cliente da distribuição');
    removeButton.appendChild(createIcon('trash'));
    removeButton.addEventListener('click', () => onRemove(uc.ucId));
    row.append(
      createElement('span', { className: 'rateio-distribuicao-texto', textContent: uc.clienteNome || uc.ucCodigo }),
      createElement('span', { className: 'rateio-distribuicao-texto', textContent: uc.apelido || '-' }),
      createElement('span', { className: 'rateio-distribuicao-texto', textContent: uc.ucCodigo }),
      createElement('span', { textContent: uc.consumo != null ? `${formatNumber(uc.consumo)} kWh` : '-' }),
      createElement('span', { className: 'rateio-percentual-sugerido', textContent: `${formatNumber(uc.percentualSugerido)}%` }),
      input,
      removeButton
    );
    list.appendChild(row);
  });
  return { list, inputs };
}

function createCompetenciaField(value: string, onChange: (value: string) => void): HTMLElement {
  const field = createElement('label', { className: 'form-field' });
  const input = createElement('input'); input.type = 'month'; input.value = value;
  input.addEventListener('input', () => onChange(input.value));
  field.append(createElement('span', { textContent: 'Competência (mês de referência)' }), input);
  return field;
}
