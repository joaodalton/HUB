import { createElement } from '../dom';
import { createCheckboxField, createInput } from './formFields';
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
  const codigoAneel = createInput('Codigo ANEEL', 'text', uc?.codigoAneel ?? '', false);
  const apelido = createInput('Subnome', 'text', uc?.apelido ?? '', false);
  const documento = createInput('CPF/CNPJ da UC', 'text', uc?.documento ?? '', false);
  const endereco = createInput('Endereco', 'text', uc?.endereco ?? '', false);
  const cep = createInput('CEP', 'text', uc?.cep ?? '', false);
  const concessionaria = createInput('Concessionaria', 'text', uc?.concessionaria ?? '', false);
  const consumo = createInput('Consumo (kWh)', 'number', uc?.consumo != null ? String(uc.consumo) : '', false);
  const baseTarifaria = createTariffSelect(uc?.baseTarifaria ?? 'B1');
  const desconto = createInput('Desconto (%)', 'text', uc?.desconto ?? '', false);
  const tipoLigacao = createLigacaoSelect(uc?.tipoLigacao ?? 'Monofasico');
  const geracaoPropria = createCheckboxField('Geracao propria', uc?.geracaoPropria ?? false);
  const diaEmissaoFatura = createInput('Dia de emissao da fatura', 'number', uc?.diaEmissaoFatura != null ? String(uc.diaEmissaoFatura) : '', false);
  const inicioContrato = createInput('Inicio do contrato', 'date', uc?.inicioContrato ?? '', false);
  const terminoContrato = createInput('Termino do contrato', 'date', uc?.terminoContrato ?? '', false);
  const carenciaMeses = createInput('Carencia (meses)', 'number', uc?.carenciaMeses != null ? String(uc.carenciaMeses) : '', false);
  const percentualDescontoCarencia = createInput('Desconto na carencia (%)', 'text', uc?.percentualDescontoCarencia ?? '', false);

  diaEmissaoFatura.input.min = '1';
  diaEmissaoFatura.input.max = '31';
  carenciaMeses.input.min = '0';

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
    codigoAneel.field,
    apelido.field,
    documento.field,
    endereco.field,
    cep.field,
    concessionaria.field,
    consumo.field,
    baseTarifaria.field,
    desconto.field,
    tipoLigacao.field,
    geracaoPropria.field,
    diaEmissaoFatura.field,
    inicioContrato.field,
    terminoContrato.field,
    carenciaMeses.field,
    percentualDescontoCarencia.field
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
      codigoAneel: codigoAneel.input.value.trim() || null,
      apelido: apelido.input.value.trim(),
      documento: documento.input.value.trim() || null,
      endereco: endereco.input.value.trim() || null,
      cep: cep.input.value.trim() || null,
      concessionaria: concessionaria.input.value.trim() || null,
      geracaoPropria: geracaoPropria.input.checked,
      diaEmissaoFatura: diaEmissaoFatura.input.value.trim() ? Number(diaEmissaoFatura.input.value) : null,
      consumo: consumo.input.value.trim() ? Number(consumo.input.value) : null,
      baseTarifaria: baseTarifaria.select.value,
      desconto: desconto.input.value.trim(),
      tipoLigacao: tipoLigacao.select.value,
      inicioContrato: inicioContrato.input.value || null,
      terminoContrato: terminoContrato.input.value || null,
      carenciaMeses: carenciaMeses.input.value.trim() ? Number(carenciaMeses.input.value) : null,
      percentualDescontoCarencia: percentualDescontoCarencia.input.value.trim() || null,
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