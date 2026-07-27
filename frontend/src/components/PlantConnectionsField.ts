import { createElement } from '../dom';
import type { PlantConnection } from '../services/clientsService';
import type { PlantRow } from '../services/plantService';

const TARIFF_OPTIONS = ['A1', 'A2', 'A3', 'A3a', 'AS', 'B1', 'B2', 'B3', 'B4'];

export function createTariffSelect(value: string) {
  const field = createElement('label', { className: 'form-field tariff-field' });
  const labelRow = createElement('span', { className: 'tariff-label' });
  const labelText = createElement('span', { textContent: 'Base tarifaria' });
  const help = createElement('span', { className: 'help-icon', textContent: '?' });
  const select = createElement('select');

  help.title = 'A1 a AS: alta tensao por nivel de fornecimento. B1 residencial, B2 rural, B3 demais classes, B4 iluminacao publica.';

  TARIFF_OPTIONS.forEach((optionValue) => {
    const option = createElement('option', { textContent: optionValue });
    option.value = optionValue;
    select.appendChild(option);
  });

  select.value = TARIFF_OPTIONS.includes(value) ? value : 'B1';
  labelRow.append(labelText, help);
  field.append(labelRow, select);

  return { field, select };
}

// Qualquer objeto que tenha uma lista de conexoes UC<->Usina (ClientUc aninhado
// no ClientCard, ou o estado local da tela de UC avulsa) serve aqui.
type HasConnections = { conexoes: PlantConnection[] };

export function createPlantConnections<T extends HasConnections>(
  target: T,
  availablePlants: PlantRow[]
): HTMLElement {
  const wrapper = createElement('div', { className: 'plant-connection-panel' });
  const title = createElement('span', {
    className: 'plant-connection-title',
    textContent: 'Conectar usinas'
  });

  wrapper.appendChild(title);

  if (availablePlants.length === 0) {
    wrapper.appendChild(createElement('p', {
      className: 'empty-state small',
      textContent: 'Nenhuma usina com percentual disponivel.'
    }));
    return wrapper;
  }

  availablePlants.forEach((plant) => {
    const existingConnection = target.conexoes.find((connection) => connection.plantId === plant.id);
    const row = createElement('label', { className: 'plant-connection-row' });
    const checkbox = createElement('input');
    const info = createElement('span', {
      textContent: `${plant.nome} - ${plant.percentualDisponivel}% disponivel`
    });
    const percent = createElement('input');

    checkbox.type = 'checkbox';
    checkbox.checked = Boolean(existingConnection);
    percent.type = 'number';
    percent.min = '0';
    percent.max = String(plant.percentualDisponivel);
    percent.placeholder = '%';
    percent.value = existingConnection?.percentual ?? '';
    percent.disabled = !checkbox.checked;

    checkbox.addEventListener('change', () => {
      percent.disabled = !checkbox.checked;
      updateConnection(target, plant, checkbox.checked, percent.value);
    });
    percent.addEventListener('input', () => {
      updateConnection(target, plant, checkbox.checked, percent.value);
    });

    row.append(checkbox, info, percent);
    wrapper.appendChild(row);
  });

  return wrapper;
}

function updateConnection(
  target: HasConnections,
  plant: PlantRow,
  enabled: boolean,
  percentual: string
): void {
  const existingIndex = target.conexoes.findIndex((connection) => connection.plantId === plant.id);

  if (!enabled) {
    if (existingIndex >= 0) target.conexoes.splice(existingIndex, 1);
    return;
  }

  const connection: PlantConnection = { plantId: plant.id, usina: plant.nome, percentual };

  if (existingIndex >= 0) {
    target.conexoes[existingIndex] = connection;
  } else {
    target.conexoes.push(connection);
  }
}
