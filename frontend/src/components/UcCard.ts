import { createElement } from '../dom';
import { createPlantConnections, createTariffSelect } from './PlantConnectionsField';
import type { ClientRow, PlantConnection } from '../services/clientsService';
import type { PlantRow } from '../services/plantService';
import type { UcPayload, UcRow } from '../services/ucsService';

type UcCardOptions = {
  uc?: UcRow;
  clients: ClientRow[];
  availablePlants: PlantRow[];
  onSave: (data: UcPayload) => void;
  onCancel: () => void;
  onDelete?: () => void;
};

const tiposLigacao = ['Monofasico', 'Bifasico', 'Trifasico'] as const;

export function createUcCard({ uc, clients, availablePlants, onSave, onCancel, onDelete }: UcCardOptions): HTMLElement {
  const overlay = createElement('section', { className: 'modal-overlay' });
  const panel = createElement('article', { className: 'plant-card' });
  const form = createElement('form', { className: 'client-form' });
  const header = createElement('div', { className: 'form-header' });
  const titleText = createElement('div');
  const eyebrow = createElement('span', { className: 'eyebrow', textContent: uc ? 'UC' : 'Nova UC' });
  const heading = createElement('h2', { textContent: uc ? uc.codigo || 'UC' : 'Cadastrar UC' });
  const closeButton = createElement('button', {
    className: 'secondary-button',
    textContent: 'Fechar',
    type: 'button'
  });
  const fields = createElement('div', { className: 'form-grid' });

  const cliente = createClientSelect(clients, uc?.clienteId);
  const codigo = createInput('UC', 'text', uc?.codigo ?? '', true);
  const apelido = createInput('Subnome', 'text', uc?.apelido ?? '', false);
  const consumo = createInput('Consumo', 'text', uc?.consumo ?? '', false);
  const baseTarifaria = createTariffSelect(uc?.baseTarifaria ?? 'B1');
  const desconto = createInput('Desconto (%)', 'text', uc?.desconto ?? '', false);
  const tipoLigacao = createLigacaoSelect(uc?.tipoLigacao ?? 'Monofasico');

  // Estado local das conexoes, no mesmo formato que createPlantConnections espera.
  const connectionState: { conexoes: PlantConnection[] } = {
    conexoes: (uc?.conexoes ?? []).map((conexao) => ({ ...conexao }))
  };
  const plantArea = createPlantConnections(connectionState, availablePlants);

  const actions = createElement('div', { className: 'form-actions' });
  const saveButton = createElement('button', { textContent: 'Salvar UC', type: 'submit' });

  titleText.append(eyebrow, heading);
  header.append(titleText, closeButton);
  fields.append(
    cliente.field,
    codigo.field,
    apelido.field,
    consumo.field,
    baseTarifaria.field,
    desconto.field,
    tipoLigacao.field
  );
  actions.appendChild(saveButton);

  if (uc && onDelete) {
    const deleteButton = createElement('button', {
      className: 'danger-button',
      textContent: 'Excluir UC',
      type: 'button'
    });

    deleteButton.addEventListener('click', onDelete);
    actions.appendChild(deleteButton);
  }

  let isSubmitting = false;

  closeButton.addEventListener('click', onCancel);
  overlay.addEventListener('click', (event) => {
    if (event.target === overlay) onCancel();
  });

  form.addEventListener('submit', (event) => {
    event.preventDefault();

    if (isSubmitting) return;

    if (!cliente.select.value || !codigo.input.value.trim()) {
      cliente.select.reportValidity();
      codigo.input.reportValidity();
      return;
    }

    isSubmitting = true;
    saveButton.disabled = true;
    saveButton.textContent = 'Salvando...';

    onSave({
      clienteId: Number(cliente.select.value),
      codigo: codigo.input.value.trim(),
      apelido: apelido.input.value.trim(),
      consumo: consumo.input.value.trim(),
      baseTarifaria: baseTarifaria.select.value,
      desconto: desconto.input.value.trim(),
      tipoLigacao: tipoLigacao.select.value,
      conexoes: connectionState.conexoes
    });
  });

  form.append(header, fields, plantArea, actions);
  panel.appendChild(form);
  overlay.appendChild(panel);

  return overlay;
}

function createClientSelect(clients: ClientRow[], selectedId?: number) {
  const field = createElement('label', { className: 'form-field' });
  const text = createElement('span', { textContent: 'Cliente' });
  const select = createElement('select');
  const placeholder = createElement('option', { textContent: 'Selecione um cliente' });

  placeholder.value = '';
  select.appendChild(placeholder);

  clients.forEach((client) => {
    const option = createElement('option', { textContent: client.nome });
    option.value = String(client.id);
    select.appendChild(option);
  });

  select.value = selectedId ? String(selectedId) : '';
  select.required = true;

  field.append(text, select);
  return { field, select };
}

function createLigacaoSelect(value: UcRow['tipoLigacao']) {
  const field = createElement('label', { className: 'form-field' });
  const text = createElement('span', { textContent: 'Ligacao' });
  const select = createElement('select');

  tiposLigacao.forEach((optionValue) => {
    const option = createElement('option', { textContent: optionValue });
    option.value = optionValue;
    select.appendChild(option);
  });

  select.value = value;
  field.append(text, select);
  return { field, select };
}

function createInput(label: string, type: string, value: string, required: boolean) {
  const field = createElement('label', { className: 'form-field' });
  const text = createElement('span', { textContent: label });
  const input = createElement('input');

  input.type = type;
  input.value = value;
  input.required = required;

  field.append(text, input);
  return { field, input };
}