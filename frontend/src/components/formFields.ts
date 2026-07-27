// frontend/src/components/formFields.ts
// Helpers de formulario reaproveitados por ClientCard e UcCard.
// Nao duplicar essas funcoes em outro componente -- importar daqui.
import { createElement } from '../dom';
import type { PlantConnection } from '../services/clientsService';
import type { PlantRow } from '../services/plantService';

export function createInput(label: string, type: string, value: string, required: boolean) {
  const field = createElement('label', { className: 'form-field' });
  const text = createElement('span', { textContent: label });
  const input = createElement('input');

  input.type = type;
  input.value = value;
  input.required = required;

  field.append(text, input);
  return { field, input };
}

export function createSelect<T extends string>(label: string, value: T, options: T[]) {
  const field = createElement('label', { className: 'form-field' });
  const text = createElement('span', { textContent: label });
  const select = createElement('select');

  options.forEach((optionValue) => {
    const option = createElement('option', { textContent: optionValue });
    option.value = optionValue;
    select.appendChild(option);
  });

  select.value = value;
  field.append(text, select);
  return { field, select };
}

export function createTariffSelect(value: string) {
  const field = createElement('label', { className: 'form-field tariff-field' });
  const labelRow = createElement('span', { className: 'tariff-label' });
  const labelText = createElement('span', { textContent: 'Base tarifaria' });
  const help = createElement('span', { className: 'help-icon', textContent: '?' });
  const select = createElement('select');
  const options = ['A1', 'A2', 'A3', 'A3a', 'AS', 'B1', 'B2', 'B3', 'B4'];

  help.title = 'A1 a AS: alta tensao por nivel de fornecimento. B1 residencial, B2 rural, B3 demais classes, B4 iluminacao publica.';

  options.forEach((optionValue) => {
    const option = createElement('option', { textContent: optionValue });
    option.value = optionValue;
    select.appendChild(option);
  });

  select.value = options.includes(value) ? value : 'B1';
  labelRow.append(labelText, help);
  field.append(labelRow, select);

  return { field, select };
}

/**
 * Painel de conexoes UC<->Usina. Opera diretamente sobre o array `connections`
 * (push/splice), no mesmo padrao usado pelo editor de UCs dentro do cliente.
 * Reaproveitado por ClientCard (UC aninhada) e UcCard (UC avulsa).
 */
export function createPlantConnections(connections: PlantConnection[], availablePlants: PlantRow[]): HTMLElement {
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
    const existingConnection = connections.find((connection) => connection.plantId === plant.id);
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
      updateConnection(connections, plant, checkbox.checked, percent.value);
    });
    percent.addEventListener('input', () => {
      updateConnection(connections, plant, checkbox.checked, percent.value);
    });

    row.append(checkbox, info, percent);
    wrapper.appendChild(row);
  });

  return wrapper;
}

function updateConnection(connections: PlantConnection[], plant: PlantRow, enabled: boolean, percentual: string): void {
  const existingIndex = connections.findIndex((connection) => connection.plantId === plant.id);

  if (!enabled) {
    if (existingIndex >= 0) connections.splice(existingIndex, 1);
    return;
  }

  const connection: PlantConnection = { plantId: plant.id, usina: plant.nome, percentual };

  if (existingIndex >= 0) {
    connections[existingIndex] = connection;
  } else {
    connections.push(connection);
  }
}