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

// SOMENTE LEITURA (corrigido 2026-08-15) -- antes esse painel tinha uma
// caixinha que, ao marcar, já criava a PlantConnection na hora, direto pelo
// formulário de UC/Cliente. Isso furava o funil de qualificação do Rateio:
// a UC "sumia" da Tela 3 (candidatas) mesmo sem ninguém ter passado pelo
// wizard e definido percentual de verdade. Conectar UC a usina agora só
// acontece via RateioPage.ts -> POST /rateio/confirmar. Aqui só mostramos
// o que já está conectado (nome da usina + % atual).
export function createPlantConnections<T extends HasConnections>(
  target: T,
  availablePlants: PlantRow[]
): HTMLElement {
  const wrapper = createElement('div', { className: 'plant-connection-panel' });
  const title = createElement('span', {
    className: 'plant-connection-title',
    textContent: 'Usinas conectadas'
  });

  wrapper.appendChild(title);

  if (target.conexoes.length === 0) {
    wrapper.appendChild(createElement('p', {
      className: 'empty-state small',
      textContent: 'Nenhuma usina conectada ainda. Use a tela de Rateio para conectar.'
    }));
    return wrapper;
  }

  target.conexoes.forEach((connection) => {
    // availablePlants só traz usinas com percentual disponível > 0 -- uma
    // usina já totalmente alocada não aparece aqui, então cai no fallback
    // do nome salvo na própria conexão (connection.usina).
    const plant = availablePlants.find((item) => item.id === connection.plantId);
    const row = createElement('div', { className: 'plant-connection-row plant-connection-row-readonly' });
    const info = createElement('span', { textContent: plant ? plant.nome : connection.usina });
    const percent = createElement('span', {
      className: 'plant-connection-percent',
      textContent: `${connection.percentual}%`
    });

    row.append(info, percent);
    wrapper.appendChild(row);
  });

  return wrapper;
}
