import { createElement } from '../dom';
import { createInput, createSelect } from './formFields';
import type { PlantRow } from '../services/plantService';

export type PlantFormData = {
  nome: string;
  uc: string;
  kwPico: string;
  status: string;
  percentualDisponivel: number;
  marcaInversor: string;
  telefoneProprietario: string;
  emailProprietario: string;
  cidade: string;
  uf: string;
  endereco: string;
  dataAtivacao: string;
  responsavel: string;
  numModulos: number | null;
  producaoMediaManual: number | null;
  diaEmissaoUsina: number | null;
};

type PlantCardOptions = {
  plant?: PlantRow;
  onSave: (data: PlantFormData) => void;
  onCancel: () => void;
  onDelete?: () => void;
};

const plantStatuses = ['Online', 'Implantacao', 'Manutencao', 'Inativa'];

export function createPlantCard({ plant, onSave, onCancel, onDelete }: PlantCardOptions): HTMLElement {
  const overlay = createElement('section', { className: 'modal-overlay' });
  const panel = createElement('article', { className: 'plant-card' });
  const form = createElement('form', { className: 'client-form' });
  const header = createElement('div', { className: 'form-header' });
  const titleText = createElement('div');
  const eyebrow = createElement('span', { className: 'eyebrow', textContent: plant ? 'Usina' : 'Nova usina' });
  const heading = createElement('h2', { textContent: plant?.nome ?? 'Cadastrar usina' });
  const closeButton = createElement('button', {
    className: 'secondary-button',
    textContent: 'Fechar',
    type: 'button'
  });
  const fields = createElement('div', { className: 'form-grid' });
  const nome = createInput('Nome', 'text', plant?.nome ?? '', true);
  const uc = createInput('UC', 'text', plant?.uc ?? '', true);
  const kwPico = createInput('kW pico', 'number', plant?.kwPico ?? '', true);
  const status = createSelect('Status', plant?.status ?? 'Online', plantStatuses);
  const percentualDisponivel = createInput(
    'Disponivel para rateio (%)',
    'number',
    String(plant?.percentualDisponivel ?? 0),
    true
  );
  const marcaInversor = createInput('Marca do inversor', 'text', plant?.marcaInversor ?? '', false);
  const telefoneProprietario = createInput('Telefone do proprietario', 'tel', plant?.telefoneProprietario ?? '', false);
  const emailProprietario = createInput('Email do proprietario', 'email', plant?.emailProprietario ?? '', false);
  const cidade = createInput('Cidade', 'text', plant?.cidade ?? '', false);
  const uf = createInput('UF', 'text', plant?.uf ?? '', false);
  const endereco = createInput('Endereco', 'text', plant?.endereco ?? '', false);
  const dataAtivacao = createInput('Data de ativacao', 'date', plant?.dataAtivacao ?? '', false);
  const responsavel = createInput('Responsavel', 'text', plant?.responsavel ?? '', false);
  const numModulos = createInput('Número de módulos', 'number', plant?.numModulos != null ? String(plant.numModulos) : '', false);
  const producaoMediaManual = createInput(
    'Produção média (kWh)',
    'number',
    plant?.producaoMediaManual != null ? String(plant.producaoMediaManual) : '',
    false
  );
  const diaEmissaoUsina = createInput(
    'Dia de emissão/leitura',
    'number',
    plant?.diaEmissaoUsina != null ? String(plant.diaEmissaoUsina) : '',
    false
  );
  const actions = createElement('div', { className: 'form-actions' });
  const saveButton = createElement('button', { textContent: 'Salvar usina', type: 'submit' });

  kwPico.input.min = '0';
  percentualDisponivel.input.min = '0';
  percentualDisponivel.input.max = '100';
  uf.input.maxLength = 2;
  numModulos.input.min = '0';
  producaoMediaManual.input.min = '0';
  producaoMediaManual.input.step = '0.01';
  producaoMediaManual.input.placeholder = 'Deixe em branco pra calcular pela produção mensal cadastrada';
  diaEmissaoUsina.input.min = '1';
  diaEmissaoUsina.input.max = '31';
  diaEmissaoUsina.input.placeholder = 'Dia do mês (1-31)';

  titleText.append(eyebrow, heading);
  header.append(titleText, closeButton);
  fields.append(
    nome.field,
    uc.field,
    kwPico.field,
    status.field,
    percentualDisponivel.field,
    marcaInversor.field,
    telefoneProprietario.field,
    emailProprietario.field,
    cidade.field,
    uf.field,
    endereco.field,
    dataAtivacao.field,
    responsavel.field,
    numModulos.field,
    producaoMediaManual.field,
    diaEmissaoUsina.field
  );
  actions.appendChild(saveButton);

  if (plant && onDelete) {
    const deleteButton = createElement('button', {
      className: 'danger-button',
      textContent: 'Excluir usina',
      type: 'button'
    });

    deleteButton.addEventListener('click', onDelete);
    actions.appendChild(deleteButton);
  }

  closeButton.addEventListener('click', onCancel);
  overlay.addEventListener('click', (event) => {
    if (event.target === overlay) onCancel();
  });
  form.addEventListener('submit', (event) => {
    event.preventDefault();

    if (!nome.input.value.trim() || !uc.input.value.trim() || !kwPico.input.value.trim()) {
      nome.input.reportValidity();
      uc.input.reportValidity();
      kwPico.input.reportValidity();
      return;
    }

    onSave({
      nome: nome.input.value.trim(),
      uc: uc.input.value.trim(),
      kwPico: kwPico.input.value.trim(),
      status: status.select.value,
      percentualDisponivel: clampPercent(Number(percentualDisponivel.input.value)),
      marcaInversor: marcaInversor.input.value.trim(),
      telefoneProprietario: telefoneProprietario.input.value.trim(),
      emailProprietario: emailProprietario.input.value.trim(),
      cidade: cidade.input.value.trim(),
      uf: uf.input.value.trim().toUpperCase(),
      endereco: endereco.input.value.trim(),
      dataAtivacao: dataAtivacao.input.value,
      responsavel: responsavel.input.value.trim(),
      numModulos: numModulos.input.value.trim() ? Number(numModulos.input.value) : null,
      producaoMediaManual: producaoMediaManual.input.value.trim() ? Number(producaoMediaManual.input.value) : null,
      diaEmissaoUsina: diaEmissaoUsina.input.value.trim() ? Number(diaEmissaoUsina.input.value) : null
    });
  });

  form.append(header, fields, actions);
  panel.appendChild(form);
  overlay.appendChild(panel);

  return overlay;
}

function clampPercent(value: number): number {
  if (Number.isNaN(value)) return 0;
  return Math.min(100, Math.max(0, value));
}