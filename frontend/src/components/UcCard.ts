// frontend/src/components/UcCard.ts
import { createInput, createPlantConnections, createSelect, createTariffSelect } from './formFields';
import { createElement } from '../dom';
import type { ClientRow, PlantConnection } from '../services/clientsService';
import type { PlantRow } from '../services/plantService';
import type { UcRow } from '../services/ucService';

export type UcFormData = {
  clienteId: number;
  codigo: string;
  apelido: string;
  consumo: string;
  baseTarifaria: string;
  desconto: string;
  tipoLigacao: string;
  conexoes: PlantConnection[];
};

type UcCardOptions = {
  uc?: UcRow;
  clients: ClientRow[];
  availablePlants: PlantRow[];
  onSave: (data: UcFormData) => void;
  onCancel: () => void;
  onDelete?: () => void;
};

export function createUcCard({
  uc,
  clients,
  availablePlants,
  onSave,
  onCancel,
  onDelete
}: UcCardOptions): HTMLElement {
  const isEditing = Boolean(uc);
  const currentConexoes: PlantConnection[] = [...(uc?.conexoes ?? [])];
  const overlay = createElement('section', { className: 'modal-overlay' });
  const panel = createElement('article', { className: 'client-card' });
  const form = createElement('form', { className: 'client-form' });
  const header = createElement('div', { className: 'form-header' });
  const titleText = createElement('div');
  const eyebrow = createElement('span', { className: 'eyebrow', textContent: isEditing ? 'UC' : 'Nova UC' });
  const heading = createElement('h2', { textContent: isEditing ? (uc?.codigo || 'UC') : 'Cadastrar UC' });
  const closeButton = createElement('button', { className: 'secondary-button', textContent: 'Fechar', type: 'button' });
  const fields = createElement('div', { className: 'form-grid' });

  const clienteOptions = clients.map((client) => String(client.id));
  const clienteLabels = new Map(clients.map((client) => [String(client.id), client.nome]));
  const cliente = createSelect(
    'Cliente',
    uc ? String(uc.clienteId) : clienteOptions[0] ?? '',
    clienteOptions
  );
  const codigo = createInput('Codigo da UC', 'text', uc?.codigo ?? '', true);
  const apelido = createInput('Subnome', 'text', uc?.apelido ?? '', false);
  const consumo = createInput('Consumo', 'text', uc?.consumo ?? '', false);
  const baseTarifaria = createTariffSelect(uc?.baseTarifaria ?? 'B1');
  const desconto = createInput('Desconto', 'text', uc?.desconto ?? '', false);
  const tipoLigacao = createSelect('Ligacao', uc?.tipoLigacao ?? 'Monofasico', ['Monofasico', 'Bifasico', 'Trifasico']);
  const plantArea = createPlantConnections(currentConexoes, availablePlants);
  const actions = createElement('div', { className: 'form-actions' });
  const saveButton = createElement('button', { textContent: 'Salvar UC', type: 'submit' });

  cliente.select.querySelectorAll('option').forEach((option) => {
    option.textContent = clienteLabels.get(option.value) ?? option.value;
  });

  titleText.append(eyebrow, heading);
  header.append(titleText, closeButton);
  fields.append(cliente.field, codigo.field, apelido.field, consumo.field, baseTarifaria.field, desconto.field, tipoLigacao.field);
  actions.appendChild(saveButton);

  if (isEditing && onDelete) {
    const deleteButton = createElement('button', { className: 'danger-button', textContent: 'Excluir UC', type: 'button' });
    deleteButton.addEventListener('click', onDelete);
    actions.appendChild(deleteButton);
  }

  closeButton.addEventListener('click', onCancel);
  form.addEventListener('submit', (event) => {
    event.preventDefault();

    if (!cliente.select.value || !codigo.input.value.trim()) {
      codigo.input.reportValidity();
      return;
    }

    onSave({
      clienteId: Number(cliente.select.value),
      codigo: codigo.input.value.trim(),
      apelido: apelido.input.value.trim(),
      consumo: consumo.input.value,
      baseTarifaria: baseTarifaria.select.value,
      desconto: desconto.input.value,
      tipoLigacao: tipoLigacao.select.value,
      conexoes: currentConexoes
    });
  });

  form.append(header, fields, plantArea, actions);
  panel.appendChild(form);

  overlay.addEventListener('click', (event) => {
    if (event.target === overlay) onCancel();
  });

  overlay.appendChild(panel);
  return overlay;
}