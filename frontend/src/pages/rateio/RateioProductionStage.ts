import { createIconStatCard } from '../../components/IconStatCard';
import { createElement } from '../../dom';
import type { PlantRow } from '../../services/plantService';
import type { RateioPreview } from '../../services/rateioService';
import { formatNumber, round2 } from './shared';

const RESERVA_PRESETS = [0, 5, 10, 15];

type Props = {
  plant: PlantRow;
  preview: RateioPreview | null;
  previewLoading: boolean;
  reservaCustomMode: boolean;
  onBack: () => void;
  onContinue: () => void;
  onCustomMode: () => void;
  onSaveReserva: (value: number) => void;
};

export function renderRateioProductionStage(props: Props): HTMLElement {
  const { plant, preview, previewLoading, reservaCustomMode, onBack, onContinue, onCustomMode, onSaveReserva } = props;
  const wrapper = createElement('section', { className: 'content-stack' });
  const panel = createElement('section', { className: 'data-panel rateio-producao' });
  const titleText = createElement('div');
  titleText.append(
    createElement('span', { className: 'eyebrow', textContent: plant.nome }),
    createElement('h2', { textContent: 'Produção disponível para o ciclo' })
  );
  panel.appendChild(createPanelTitle(titleText));

  if (previewLoading || !preview) {
    panel.appendChild(createElement('p', { className: 'settings-hint', textContent: 'Calculando...' }));
  } else {
    const reservaKwh = round2(preview.producaoMedia - preview.producaoDisponivel);
    const statsGrid = createElement('div', { className: 'rateio-producao-stats' });
    statsGrid.append(
      createProducaoStat('Disponível', `${formatNumber(preview.producaoMedia)} kWh`, 'neutral'),
      createProducaoStat(`Reserva (${preview.reservaPercentual}%)`, `${formatNumber(reservaKwh)} kWh`, 'warning'),
      createProducaoStat('Para rateio', `${formatNumber(preview.producaoDisponivel)} kWh`, 'success')
    );
    panel.appendChild(statsGrid);
    if (preview.warnings.length) {
      const warnings = createElement('div', { className: 'rateio-warnings' });
      preview.warnings.forEach((warning) => warnings.appendChild(createElement('p', { textContent: `⚠ ${warning}` })));
      panel.appendChild(warnings);
    }
  }

  panel.append(createReservaField(plant, reservaCustomMode, onCustomMode, onSaveReserva), createProducaoMediaHint(plant));
  const actions = createElement('div', { className: 'form-actions' });
  const back = createElement('button', { className: 'secondary-button', textContent: '← Voltar', type: 'button' });
  const next = createElement('button', { textContent: 'Continuar →', type: 'button' });
  back.addEventListener('click', onBack);
  next.addEventListener('click', onContinue);
  actions.append(back, next);
  wrapper.append(panel, actions);
  return wrapper;
}

function createPanelTitle(titleText: HTMLElement): HTMLElement {
  const title = createElement('div', { className: 'panel-title' });
  title.appendChild(titleText);
  return title;
}

function createProducaoStat(label: string, value: string, tone: 'neutral' | 'warning' | 'success'): HTMLElement {
  return createIconStatCard({
    label,
    value,
    icon: tone === 'warning' ? 'pending' : tone === 'success' ? 'check' : 'plants',
    chipColor: tone === 'warning' ? 'amber' : tone === 'success' ? 'green' : 'blue'
  });
}

function createReservaField(plant: PlantRow, customMode: boolean, onCustomMode: () => void, onSave: (value: number) => void): HTMLElement {
  const field = createElement('div', { className: 'rateio-reserva-field' });
  field.appendChild(createElement('span', { className: 'settings-subheading', textContent: 'Estratégia de reserva' }));
  const buttons = createElement('div', { className: 'rateio-reserva-buttons' });
  RESERVA_PRESETS.forEach((value) => {
    const button = createElement('button', {
      className: !customMode && plant.reservaPercentual === value ? 'small-button active' : 'small-button',
      textContent: `${value}%`, type: 'button'
    });
    button.addEventListener('click', () => onSave(value));
    buttons.appendChild(button);
  });
  const custom = createElement('button', { className: customMode ? 'small-button active' : 'small-button', textContent: 'Personalizado', type: 'button' });
  custom.addEventListener('click', onCustomMode);
  buttons.appendChild(custom);
  field.appendChild(buttons);
  if (customMode) {
    const row = createElement('div', { className: 'rateio-custom-row' });
    const input = createElement('input');
    input.type = 'number'; input.min = '0'; input.max = '100'; input.step = '0.5'; input.value = String(plant.reservaPercentual);
    const save = createElement('button', { className: 'small-button', textContent: 'Salvar', type: 'button' });
    save.addEventListener('click', () => onSave(Number(input.value) || 0));
    row.append(input, save); field.appendChild(row);
  }
  return field;
}

function createProducaoMediaHint(plant: PlantRow): HTMLElement {
  return createElement('p', {
    className: 'settings-hint',
    textContent: plant.producaoMediaManual != null
      ? `Produção média definida manualmente: ${formatNumber(plant.producaoMediaManual)} kWh. Para alterar, edite a usina em "Usinas".`
      : 'Produção média calculada pela média dos meses cadastrados. Para definir um valor manual ou cadastrar produção mensal, edite a usina em "Usinas".'
  });
}
