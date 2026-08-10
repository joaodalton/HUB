import { createElement } from '../dom';
import { createClientDocumentsPanel } from './ClientDocumentsPanel';
import { createCheckboxField, createInput, createSelect } from './formFields';
import { createPlantConnections, createTariffSelect } from './PlantConnectionsField';
import { concessionarias, type ClientRow, type ClientUc } from '../services/clientsService';
import type { PlantRow } from '../services/plantService';

export type ClientFormData = {
  nome: string;
  cpf: string;
  email: string;
  telefone: string;
  dataNascimento: string;
  concessionaria: string;
  ucs: ClientUc[];
};

type ClientCardOptions = {
  client?: ClientRow;
  availablePlants: PlantRow[];
  onSave: (data: ClientFormData) => void;
  onCancel: () => void;
  onDelete?: () => void;
};

export function createClientCard({
  client,
  availablePlants,
  onSave,
  onCancel,
  onDelete
}: ClientCardOptions): HTMLElement {
  const isEditing = Boolean(client);
  const currentUcs = [...(client?.ucs ?? [])];
  const overlay = createElement('section', { className: 'modal-overlay' });
  const panel = createElement('article', {
    className: isEditing ? 'client-card client-card-split' : 'client-card'
  });
  const left = createElement('form', { className: 'client-form' });
  const header = createElement('div', { className: 'form-header' });
  const titleText = createElement('div');
  const eyebrow = createElement('span', {
    className: 'eyebrow',
    textContent: isEditing ? 'Cliente' : 'Novo cliente'
  });
  const heading = createElement('h2', {
    textContent: isEditing ? client?.nome ?? 'Cliente' : 'Cadastrar cliente'
  });
  const closeButton = createElement('button', {
    className: 'secondary-button',
    textContent: 'Fechar',
    type: 'button'
  });
  const fields = createElement('div', { className: 'form-grid' });
  const nome = createInput('Nome', 'text', client?.nome ?? '', true);
  const cpf = createInput('CPF', 'text', client?.cpf ?? '', true);
  const telefone = createInput('Telefone', 'tel', client?.telefone ?? '', false);
  const email = createInput('Email', 'email', client?.email ?? '', true);
  const dataNascimento = createInput('Data de nascimento', 'date', client?.dataNascimento ?? '', false);
  const concessionaria = createSelect('Concessionaria', client?.concessionaria ?? concessionarias[0], concessionarias);
  const documentsPanel = createClientDocumentsPanel(client?.id);
  const actions = createElement('div', { className: 'form-actions' });
  const saveButton = createElement('button', { textContent: 'Salvar cliente', type: 'submit' });
  const ucPanel = createUcPanel(currentUcs, availablePlants);

  titleText.append(eyebrow, heading);
  header.append(titleText, closeButton);
  fields.append(nome.field, cpf.field, telefone.field, email.field, dataNascimento.field, concessionaria.field);
  actions.appendChild(saveButton);

  if (isEditing && onDelete) {
    const deleteButton = createElement('button', {
      className: 'danger-button',
      textContent: 'Excluir cliente',
      type: 'button'
    });

    deleteButton.addEventListener('click', onDelete);
    actions.appendChild(deleteButton);
  }

  let isSubmitting = false;

  closeButton.addEventListener('click', onCancel);
  left.addEventListener('submit', async (event) => {
    event.preventDefault();

    if (isSubmitting) return;

    if (!nome.input.value.trim() || !cpf.input.value.trim() || !email.input.value.trim()) {
      nome.input.reportValidity();
      cpf.input.reportValidity();
      email.input.reportValidity();
      return;
    }

    isSubmitting = true;
    saveButton.disabled = true;
    saveButton.textContent = 'Salvando...';

    onSave({
      nome: nome.input.value.trim(),
      cpf: cpf.input.value.trim(),
      email: email.input.value.trim(),
      telefone: telefone.input.value.trim(),
      dataNascimento: dataNascimento.input.value,
      concessionaria: concessionaria.select.value,
      ucs: currentUcs.filter((uc) => uc.codigo.trim())
    });
  });

  left.append(header, fields, documentsPanel, actions);
  panel.appendChild(left);

  panel.appendChild(ucPanel);

  overlay.addEventListener('click', (event) => {
    if (event.target === overlay) onCancel();
  });

  overlay.appendChild(panel);
  return overlay;
}

function createUcPanel(ucs: ClientUc[], availablePlants: PlantRow[]): HTMLElement {
  const panel = createElement('aside', { className: 'client-uc-panel' });
  const title = createElement('div', { className: 'panel-title' });
  const titleText = createElement('div');
  const eyebrow = createElement('span', { className: 'eyebrow', textContent: 'UCs' });
  const heading = createElement('h2', { textContent: 'Unidades consumidoras' });
  const addButton = createElement('button', {
    className: 'small-button',
    textContent: 'Adicionar UC',
    type: 'button'
  });
  const list = createElement('div', { className: 'uc-editor-list' });

  function renderList(): void {
    list.replaceChildren();

    if (ucs.length === 0) {
      list.appendChild(createElement('p', {
        className: 'empty-state small',
        textContent: 'Nenhuma UC vinculada.'
      }));
      return;
    }

    ucs.forEach((uc) => {
      list.appendChild(createUcEditor(uc, availablePlants, () => {
        const index = ucs.findIndex((item) => item.id === uc.id);
        if (index >= 0) ucs.splice(index, 1);
        renderList();
      }));
    });
  }

  addButton.addEventListener('click', () => {
    ucs.push(createEmptyUc());
    renderList();
  });

  titleText.append(eyebrow, heading);
  title.append(titleText, addButton);
  panel.append(title, list);
  renderList();

  return panel;
}

function createUcEditor(uc: ClientUc, availablePlants: PlantRow[], onRemove: () => void): HTMLElement {
  const card = createElement('details', { className: 'uc-editor-card' });
  const summary = createElement('summary', { className: 'uc-summary' });
  const summaryTitle = createElement('strong', { textContent: uc.codigo || 'Nova UC' });
  const summaryMeta = createElement('span', { textContent: uc.apelido || 'Mais informacoes' });
  const body = createElement('div', { className: 'uc-editor-body' });
  const grid = createElement('div', { className: 'uc-editor-grid' });

  const codigo = createInput('UC', 'text', uc.codigo, false);
  const codigoAneel = createInput('Codigo ANEEL', 'text', uc.codigoAneel ?? '', false);
  const apelido = createInput('Subnome', 'text', uc.apelido, false);
  const documento = createInput('CPF/CNPJ da UC', 'text', uc.documento ?? '', false);
  const endereco = createInput('Endereco', 'text', uc.endereco ?? '', false);
  const cep = createInput('CEP', 'text', uc.cep ?? '', false);
  const concessionariaUc = createInput('Concessionaria', 'text', uc.concessionaria ?? '', false);
  const consumo = createInput('Consumo', 'text', uc.consumo, false);
  const baseTarifaria = createTariffSelect(uc.baseTarifaria);
  const desconto = createInput('Desconto (%)', 'text', uc.desconto, false);
  const tipoLigacao = createSelect('Ligacao', uc.tipoLigacao, ['Monofasico', 'Bifasico', 'Trifasico']);
  const geracaoPropria = createCheckboxField('Geracao propria', uc.geracaoPropria);
  const diaEmissaoFatura = createInput('Dia de emissao da fatura', 'number', uc.diaEmissaoFatura != null ? String(uc.diaEmissaoFatura) : '', false);
  const inicioContrato = createInput('Inicio do contrato', 'date', uc.inicioContrato ?? '', false);
  const terminoContrato = createInput('Termino do contrato', 'date', uc.terminoContrato ?? '', false);
  const carenciaMeses = createInput('Carencia (meses)', 'number', uc.carenciaMeses != null ? String(uc.carenciaMeses) : '', false);
  const percentualDescontoCarencia = createInput('Desconto na carencia (%)', 'text', uc.percentualDescontoCarencia ?? '', false);

  const removeButton = createElement('button', {
    className: 'danger-button',
    textContent: 'Remover UC',
    type: 'button'
  });
  const plantArea = createPlantConnections(uc, availablePlants);

  diaEmissaoFatura.input.min = '1';
  diaEmissaoFatura.input.max = '31';
  carenciaMeses.input.min = '0';

  codigo.input.addEventListener('input', () => {
    uc.codigo = codigo.input.value;
    summaryTitle.textContent = uc.codigo || 'Nova UC';
  });
  codigoAneel.input.addEventListener('input', () => { uc.codigoAneel = codigoAneel.input.value || null; });
  apelido.input.addEventListener('input', () => {
    uc.apelido = apelido.input.value;
    summaryMeta.textContent = uc.apelido || 'Mais informacoes';
  });
  documento.input.addEventListener('input', () => { uc.documento = documento.input.value || null; });
  endereco.input.addEventListener('input', () => { uc.endereco = endereco.input.value || null; });
  cep.input.addEventListener('input', () => { uc.cep = cep.input.value || null; });
  concessionariaUc.input.addEventListener('input', () => { uc.concessionaria = concessionariaUc.input.value || null; });
  consumo.input.addEventListener('input', () => { uc.consumo = consumo.input.value; });
  baseTarifaria.select.addEventListener('change', () => { uc.baseTarifaria = baseTarifaria.select.value; });
  desconto.input.addEventListener('input', () => { uc.desconto = desconto.input.value; });
  tipoLigacao.select.addEventListener('change', () => {
    uc.tipoLigacao = tipoLigacao.select.value as ClientUc['tipoLigacao'];
  });
  geracaoPropria.input.addEventListener('change', () => { uc.geracaoPropria = geracaoPropria.input.checked; });
  diaEmissaoFatura.input.addEventListener('input', () => {
    const raw = diaEmissaoFatura.input.value.trim();
    uc.diaEmissaoFatura = raw ? Number(raw) : null;
  });
  inicioContrato.input.addEventListener('input', () => { uc.inicioContrato = inicioContrato.input.value || null; });
  terminoContrato.input.addEventListener('input', () => { uc.terminoContrato = terminoContrato.input.value || null; });
  carenciaMeses.input.addEventListener('input', () => {
    const raw = carenciaMeses.input.value.trim();
    uc.carenciaMeses = raw ? Number(raw) : null;
  });
  percentualDescontoCarencia.input.addEventListener('input', () => {
    uc.percentualDescontoCarencia = percentualDescontoCarencia.input.value || null;
  });
  removeButton.addEventListener('click', onRemove);

  grid.append(
    codigo.field,
    codigoAneel.field,
    apelido.field,
    documento.field,
    endereco.field,
    cep.field,
    concessionariaUc.field,
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
  summary.append(summaryTitle, summaryMeta);
  body.append(grid, plantArea, removeButton);
  card.append(summary, body);

  return card;
}

function createEmptyUc(): ClientUc {
  return {
    id: crypto.randomUUID(),
    codigo: '',
    codigoAneel: null,
    apelido: '',
    documento: null,
    endereco: null,
    cep: null,
    concessionaria: null,
    geracaoPropria: false,
    diaEmissaoFatura: null,
    consumo: '',
    baseTarifaria: 'B1',
    desconto: '',
    tipoLigacao: 'Monofasico',
    inicioContrato: null,
    terminoContrato: null,
    carenciaMeses: null,
    percentualDescontoCarencia: null,
    conexoes: []
  };
}