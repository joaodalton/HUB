import { createElement } from '../dom';
import { concessionarias, type ClientDocument, type ClientRow, type ClientUc, type PlantConnection } from '../services/clientsService';
import type { PlantRow } from '../services/plantService';

export type ClientFormData = {
  nome: string;
  cpf: string;
  email: string;
  concessionaria: string;
  documentos: ClientDocument[];
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
  const currentDocuments = [...(client?.documentos ?? [])];
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
  const email = createInput('Email', 'email', client?.email ?? '', true);
  const concessionaria = createSelect('Concessionaria', client?.concessionaria ?? concessionarias[0], concessionarias);
  const documents = createDocumentPicker(currentDocuments);
  const actions = createElement('div', { className: 'form-actions' });
  const saveButton = createElement('button', { textContent: 'Salvar cliente', type: 'submit' });
  const ucPanel = createUcPanel(currentUcs, availablePlants);

  titleText.append(eyebrow, heading);
  header.append(titleText, closeButton);
  fields.append(nome.field, cpf.field, email.field, concessionaria.field, documents.field);
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

  closeButton.addEventListener('click', onCancel);
  left.addEventListener('submit', async (event) => {
    event.preventDefault();

    if (!nome.input.value.trim() || !cpf.input.value.trim() || !email.input.value.trim()) {
      nome.input.reportValidity();
      cpf.input.reportValidity();
      email.input.reportValidity();
      return;
    }

    const selectedDocuments = await readSelectedDocuments(documents.input.files);

    onSave({
      nome: nome.input.value.trim(),
      cpf: cpf.input.value.trim(),
      email: email.input.value.trim(),
      concessionaria: concessionaria.select.value,
      documentos: [...currentDocuments, ...selectedDocuments],
      ucs: currentUcs.filter((uc) => uc.codigo.trim())
    });
  });

  left.append(header, fields, actions);
  panel.appendChild(left);

  panel.appendChild(ucPanel);

  overlay.addEventListener('click', (event) => {
    if (event.target === overlay) onCancel();
  });

  overlay.appendChild(panel);
  return overlay;
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

function createSelect<T extends string>(label: string, value: T, options: T[]) {
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

function createDocumentPicker(currentDocuments: ClientDocument[]) {
  const field = createElement('label', { className: 'form-field form-field-wide' });
  const text = createElement('span', { textContent: 'Documentos' });
  const input = createElement('input');
  const list = createDocumentList(currentDocuments);
  const hint = createElement('small', { textContent: 'Anexo rapido neste formulario. Para gerenciar documentos de verdade (upload permanente, categoria, download), use a tela de Documentos.' });

  input.type = 'file';
  input.multiple = true;

  field.append(text, list, input, hint);
  return { field, input };
}

function createDocumentList(documents: ClientDocument[]): HTMLElement {
  const list = createElement('div', { className: 'document-list' });

  if (documents.length === 0) {
    list.appendChild(createElement('small', { textContent: 'Nenhum documento anexado ainda.' }));
    return list;
  }

  documents.forEach((documento) => {
    const row = createElement('div', { className: 'document-row' });
    const name = createElement('input');
    const download = createElement('button', {
      className: 'secondary-button',
      textContent: 'Baixar',
      type: 'button'
    });

    name.value = documento.nome;
    name.addEventListener('input', () => {
      documento.nome = name.value.trim() || documento.nome;
    });

    download.disabled = !documento.dataUrl;
    download.title = documento.dataUrl ? 'Baixar anexo' : 'Arquivo antigo sem conteudo salvo localmente';
    download.addEventListener('click', () => {
      if (!documento.dataUrl) return;
      downloadDocument(documento);
    });

    row.append(name, download);
    list.appendChild(row);
  });

  return list;
}

async function readSelectedDocuments(files: FileList | null): Promise<ClientDocument[]> {
  if (!files) return [];

  return Promise.all(Array.from(files).map(async (file) => ({
    id: crypto.randomUUID(),
    nome: file.name,
    dataUrl: await readFileAsDataUrl(file)
  })));
}

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();

    reader.addEventListener('load', () => resolve(String(reader.result)));
    reader.addEventListener('error', () => reject(reader.error));
    reader.readAsDataURL(file);
  });
}

function downloadDocument(documento: ClientDocument): void {
  const link = createElement('a');

  link.href = documento.dataUrl ?? '';
  link.download = documento.nome;
  document.body.appendChild(link);
  link.click();
  link.remove();
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
  const apelido = createInput('Subnome', 'text', uc.apelido, false);
  const consumo = createInput('Consumo', 'text', uc.consumo, false);
  const baseTarifaria = createTariffSelect(uc.baseTarifaria);
  const desconto = createInput('Desconto', 'text', uc.desconto, false);
  const tipoLigacao = createSelect('Ligacao', uc.tipoLigacao, ['Monofasico', 'Bifasico', 'Trifasico']);
  const removeButton = createElement('button', {
    className: 'danger-button',
    textContent: 'Remover UC',
    type: 'button'
  });
  const plantArea = createPlantConnections(uc, availablePlants);

  codigo.input.addEventListener('input', () => {
    uc.codigo = codigo.input.value;
    summaryTitle.textContent = uc.codigo || 'Nova UC';
  });
  apelido.input.addEventListener('input', () => {
    uc.apelido = apelido.input.value;
    summaryMeta.textContent = uc.apelido || 'Mais informacoes';
  });
  consumo.input.addEventListener('input', () => { uc.consumo = consumo.input.value; });
  baseTarifaria.select.addEventListener('change', () => { uc.baseTarifaria = baseTarifaria.select.value; });
  desconto.input.addEventListener('input', () => { uc.desconto = desconto.input.value; });
  tipoLigacao.select.addEventListener('change', () => {
    uc.tipoLigacao = tipoLigacao.select.value as ClientUc['tipoLigacao'];
  });
  removeButton.addEventListener('click', onRemove);

  grid.append(
    codigo.field,
    apelido.field,
    consumo.field,
    baseTarifaria.field,
    desconto.field,
    tipoLigacao.field
  );
  summary.append(summaryTitle, summaryMeta);
  body.append(grid, plantArea, removeButton);
  card.append(summary, body);

  return card;
}

function createTariffSelect(value: string) {
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

function createPlantConnections(uc: ClientUc, availablePlants: PlantRow[]): HTMLElement {
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
    const existingConnection = uc.conexoes.find((connection) => connection.plantId === plant.id);
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
      updateConnection(uc, plant, checkbox.checked, percent.value);
    });
    percent.addEventListener('input', () => {
      updateConnection(uc, plant, checkbox.checked, percent.value);
    });

    row.append(checkbox, info, percent);
    wrapper.appendChild(row);
  });

  return wrapper;
}

function updateConnection(uc: ClientUc, plant: PlantRow, enabled: boolean, percentual: string): void {
  const existingIndex = uc.conexoes.findIndex((connection) => connection.plantId === plant.id);

  if (!enabled) {
    if (existingIndex >= 0) uc.conexoes.splice(existingIndex, 1);
    return;
  }

  const connection: PlantConnection = { plantId: plant.id, usina: plant.nome, percentual };

  if (existingIndex >= 0) {
    uc.conexoes[existingIndex] = connection;
  } else {
    uc.conexoes.push(connection);
  }
}

function createEmptyUc(): ClientUc {
  return {
    id: crypto.randomUUID(),
    codigo: '',
    apelido: '',
    consumo: '',
    baseTarifaria: 'B1',
    desconto: '',
    tipoLigacao: 'Monofasico',
    conexoes: []
  };
}